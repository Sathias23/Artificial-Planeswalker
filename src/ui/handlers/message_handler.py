"""Message handling orchestration.

This module orchestrates the complete message handling workflow:
1. Display thinking message
2. Run agent with session context
3. Extract tool calls and create Chainlit Steps
4. Send agent response
5. Detect signals and delegate to signal handlers
6. Update sidebar if needed
7. Handle errors gracefully
"""

import logging
import random
from collections.abc import Awaitable, Callable

import chainlit as cl
from pydantic_ai import Agent

from src.agent.core import run_agent_with_session
from src.agent.dependencies import AgentDependencies
from src.agent.errors import AgentError, ModelUnavailableError, RateLimitError
from src.ui.action_callbacks import remove_all_actions
from src.ui.handlers.signal_handlers import (
    handle_confirmation_signal,
    handle_deck_list_signal,
    handle_disambiguation_signal,
    handle_pagination_signal,
    handle_suggestion_signal,
    handle_synergy_signal,
)
from src.ui.tool_steps import extract_tool_calls, format_tool_params, get_friendly_tool_name

logger = logging.getLogger(__name__)

# Magic-themed thinking messages for better UX
THINKING_MESSAGES = [
    "🔮 Consulting the oracle...",
    "⚡ Channeling mana...",
    "📚 Searching the archives...",
    "✨ Casting the spell...",
    "🎴 Shuffling the deck...",
    "🌟 Planeswalking through possibilities...",
]


async def handle_user_message(
    message: cl.Message,
    agent: Agent[AgentDependencies, str],
    session_id: str,
    deps: AgentDependencies,
    update_sidebar_callback: Callable[[str], Awaitable[None]],
) -> None:
    """Orchestrate message handling workflow.

    This function coordinates the complete message processing flow:
    - Shows thinking message during agent execution
    - Runs agent with session context and conversation history
    - Extracts tool calls and creates Chainlit Steps for transparency
    - Sends agent response with any UI elements
    - Detects signals and delegates to appropriate signal handlers
    - Updates sidebar if deck state changed
    - Handles errors gracefully with user-friendly messages

    Args:
        message: The incoming message from the user
        agent: The PydanticAI agent instance
        session_id: Session identifier for conversation history
        deps: Agent dependencies (repositories, session state, UI elements)
        update_sidebar_callback: Function to call for sidebar updates
    """
    user_input = message.content
    logger.info(f"Processing user message: {user_input[:100]}...")

    logger.info(
        "handle_user_message: message_id=%s, session_id=%s, user_input_length=%d",
        message.id if hasattr(message, "id") else "unknown",
        session_id,
        len(user_input),
    )

    # Display Magic-themed thinking message while agent processes request
    thinking_message_text = random.choice(THINKING_MESSAGES)
    thinking_msg = await cl.Message(content=thinking_message_text).send()

    try:
        # Run agent with session-based conversation history
        # History management is transparent - handled by run_agent_with_session
        result = await run_agent_with_session(
            user_input=user_input,
            session_id=session_id,
            deps=deps,
            agent=agent,
        )

        # Remove thinking message before displaying results
        await thinking_msg.remove()

        # Extract tool calls from result messages and create Steps for visibility
        # Use new_messages() to get ONLY current turn (not full conversation history)
        current_turn_messages = result.new_messages()
        tool_calls = extract_tool_calls(current_turn_messages)

        # Create Steps BEFORE creating/sending the response message
        # This ensures Steps appear ABOVE the streaming response in the UI
        for tool_call in tool_calls:
            tool_name = tool_call["tool_name"]
            friendly_name = get_friendly_tool_name(tool_name)

            # Create a Step showing the tool execution
            async with cl.Step(type="tool", name=friendly_name) as step:
                # Format and display tool parameters
                params_str = format_tool_params(tool_name, tool_call["args"])
                step.input = params_str

                # For now, we don't have the actual result in the MVP
                # Future enhancement: match tool calls with ToolReturnPart
                step.output = "Tool executed"

        # Check if any tool returned special signals
        confirmation_signal = None
        pagination_signal = None
        synergy_signal = None
        suggestion_signal = None
        deck_list_signal = None
        disambiguation_signal = None
        for msg in current_turn_messages:
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    # Check if this is a ToolReturnPart with dict content
                    if hasattr(part, "content") and isinstance(part.content, dict):
                        if part.content.get("needs_confirmation"):
                            confirmation_signal = part.content
                        elif part.content.get("has_pagination"):
                            pagination_signal = part.content
                        elif part.content.get("has_synergies"):
                            synergy_signal = part.content
                        elif part.content.get("has_suggestions"):
                            suggestion_signal = part.content
                        elif part.content.get("has_decks"):
                            deck_list_signal = part.content
                        elif part.content.get("needs_disambiguation"):
                            disambiguation_signal = part.content

        # NOW create the response message AFTER Steps have been created
        # This ensures correct visual ordering: Steps appear first, then response text
        # Send complete response (no streaming - it's artificial anyway since agent
        # pre-computes the response, and streaming breaks HTML tags)
        response_message = cl.Message(content=result.output)

        # Attach any UI elements collected during tool execution (e.g., card images)
        if deps.ui_elements:
            response_message.elements = deps.ui_elements

        # Update sidebar if deck state changed during tool execution
        if deps.sidebar_needs_update:
            logger.info(f"Sidebar update triggered for session {session_id}")
            # Clear synergy suggestions when deck changes
            # (prevents stale synergy buttons for previous deck)
            await remove_all_actions("synergy_suggestions_message")
            await update_sidebar_callback(session_id)

        # Send the complete message
        await response_message.send()

        # If confirmation signal detected, show action buttons
        if confirmation_signal:
            await handle_confirmation_signal(confirmation_signal)

        # If pagination signal detected, display pagination buttons
        if pagination_signal:
            await handle_pagination_signal(pagination_signal)

        # If synergy signal detected, display quick-add action buttons
        if synergy_signal:
            await handle_synergy_signal(synergy_signal)

        # If suggestion signal detected, display quick-add action buttons
        if suggestion_signal:
            await handle_suggestion_signal(suggestion_signal)

        # If deck list signal detected, display quick-load action buttons
        if deck_list_signal:
            await handle_deck_list_signal(deck_list_signal)

        # If disambiguation signal detected, display card selection action buttons
        if disambiguation_signal:
            await handle_disambiguation_signal(disambiguation_signal, user_input)

        logger.info("Agent response completed successfully")

    except RateLimitError as e:
        # Remove thinking message on error
        await thinking_msg.remove()
        error_content = """# Rate Limit Exceeded

I'm receiving too many requests right now. Please wait a moment and try again.

If this persists, you may need to check your OpenRouter account limits.
"""
        error_msg = cl.Message(content=error_content)
        await error_msg.send()
        logger.warning(f"Rate limit error: {e}")

    except ModelUnavailableError as e:
        # Remove thinking message on error
        await thinking_msg.remove()
        error_content = f"""# Model Unavailable

The AI model is temporarily unavailable:

```
{str(e)}
```

Please try again in a moment.
"""
        error_msg = cl.Message(content=error_content)
        await error_msg.send()
        logger.error(f"Model unavailable: {e}")

    except AgentError as e:
        # Remove thinking message on error
        await thinking_msg.remove()
        error_content = f"""# Agent Error

Something went wrong while processing your request:

```
{str(e)}
```

Please try rephrasing your question or try again later.
"""
        error_msg = cl.Message(content=error_content)
        await error_msg.send()
        logger.error(f"Agent error: {e}")

    except Exception as e:
        # Remove thinking message on error
        await thinking_msg.remove()
        error_content = f"""# Unexpected Error

An unexpected error occurred:

```
{str(e)}
```

Please try again or contact support if this persists.
"""
        error_msg = cl.Message(content=error_content)
        await error_msg.send()
        logger.exception("Unexpected error in message handler")

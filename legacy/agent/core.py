"""Core agent initialization and management for Artificial-Planeswalker.

This module provides factory functions for creating and configuring
PydanticAI agents with Anthropic and OpenRouter integration, along with
session-based conversation history management.
"""

import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, SystemPromptPart
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from src.data.repositories.card import FormatFilter, GamesFilter

from .config import AgentConfig
from .dependencies import AgentDependencies
from .errors import AuthenticationError

logger = logging.getLogger(__name__)


def configure_observability(config: AgentConfig) -> None:
    """Configure Pydantic Logfire observability when enabled.

    This function initializes Logfire instrumentation for the agent, database,
    and HTTP requests when observability is enabled via configuration. When
    disabled, this function returns immediately with zero overhead.

    Instrumentation includes:
    - PydanticAI agent tracing (prompts, responses, tool calls, token usage)
    - SQLAlchemy database query tracing (queries, execution time)
    - httpx HTTP request tracing (requests to external APIs)
    - Python logging integration (log-trace correlation)

    Args:
        config: Agent configuration with Logfire settings

    Raises:
        No exceptions are raised. Errors during Logfire initialization are
        logged and the application continues without observability.

    Example:
        >>> config = AgentConfig()
        >>> configure_observability(config)  # No-op if disabled
        >>> # Or with observability enabled:
        >>> config = AgentConfig(
        ...     logfire_enabled=True,
        ...     logfire_token="lf_...",
        ...     logfire_project="my-project"
        ... )
        >>> configure_observability(config)
        >>> # Now all agent runs are traced
    """
    # Skip initialization if Logfire is disabled
    if not config.logfire_enabled:
        logger.debug("Logfire observability disabled, skipping instrumentation")
        return

    try:
        # Import logfire only when enabled to avoid unnecessary dependencies
        import logfire

        # Configure Logfire with token and service name
        logfire.configure(
            token=config.logfire_token,
            service_name=config.logfire_project,
        )

        # Instrument PydanticAI for agent tracing
        logfire.instrument_pydantic_ai()

        # Instrument httpx for HTTP request tracing (e.g., Scryfall API calls)
        logfire.instrument_httpx()

        # Integrate Python logging with Logfire for log-trace correlation
        # This sends application logs to Logfire dashboard alongside traces
        logfire_handler = logfire.LogfireLoggingHandler()
        root_logger = logging.getLogger()
        root_logger.addHandler(logfire_handler)

        logger.info(f"Logfire observability enabled for project '{config.logfire_project}'")

    except Exception as e:
        # Log error but don't crash - continue without observability
        logger.error(
            f"Failed to initialize Logfire observability: {e}",
            exc_info=True,
        )
        logger.warning("Application will continue without observability")


class ConversationSessionManager:
    """Manages conversation history and session state for multiple sessions.

    This class provides session-based storage for conversation message history
    and session state (e.g., format filter preferences), enabling contextual
    conversations across multiple agent invocations within the same session.
    Sessions are identified by string IDs and stored in-memory.

    Storage is keyed by session ID with values being lists of ModelMessage objects
    from PydanticAI for message history, and FormatFilter for format preferences.
    The manager handles session creation, retrieval, updates, and cleanup transparently.

    Example:
        >>> manager = ConversationSessionManager()
        >>> history = manager.get_history("session-123")  # Returns []
        >>> messages = [...]  # From result.all_messages()
        >>> manager.update_history("session-123", messages)
        >>> history = manager.get_history("session-123")  # Returns stored messages
        >>> manager.set_format_filter("session-123", "standard")
        >>> filter = manager.get_format_filter("session-123")  # Returns "standard"
    """

    def __init__(self) -> None:
        """Initialize the session manager with empty storage."""
        self._sessions: dict[str, list[ModelMessage]] = {}
        self._format_filters: dict[str, FormatFilter] = {}
        self._games_filters: dict[str, GamesFilter] = {}
        self._active_deck_ids: dict[str, str] = {}
        self._preferences: dict[str, dict[str, bool]] = {}  # session_id -> {pref_name: value}
        self._search_contexts: dict[str, dict[str, Any]] = {}  # session_id -> search_context

    def get_history(self, session_id: str) -> list[ModelMessage]:
        """Retrieve conversation history for a session.

        Args:
            session_id: Unique identifier for the conversation session

        Returns:
            List of ModelMessage objects for the session, or empty list
            if the session doesn't exist or has no history
        """
        return self._sessions.get(session_id, [])

    def update_history(self, session_id: str, messages: list[ModelMessage]) -> None:
        """Update conversation history for a session.

        Replaces the entire message history for the session with the provided
        messages. This is typically called after each agent invocation with
        the result from result.all_messages().

        Args:
            session_id: Unique identifier for the conversation session
            messages: Complete list of ModelMessage objects to store
        """
        self._sessions[session_id] = messages

    def clear_session(self, session_id: str) -> None:
        """Clear conversation history and session state for a session.

        Removes the session and all its message history, format filter
        preference, games filter preference, active deck ID, preferences,
        and search context from storage. Safe to call even if the session doesn't exist.

        Args:
            session_id: Unique identifier for the conversation session
        """
        self._sessions.pop(session_id, None)
        self._format_filters.pop(session_id, None)
        self._games_filters.pop(session_id, None)
        self._active_deck_ids.pop(session_id, None)
        self._preferences.pop(session_id, None)
        self._search_contexts.pop(session_id, None)

    def get_format_filter(self, session_id: str) -> FormatFilter:
        """Retrieve format filter preference for a session.

        Args:
            session_id: Unique identifier for the conversation session

        Returns:
            Format filter (e.g., "standard") or None if no filter is set
        """
        return self._format_filters.get(session_id, None)

    def set_format_filter(self, session_id: str, filter_value: FormatFilter) -> None:
        """Set format filter preference for a session.

        Stores the format filter preference for the session. This allows format
        filters to persist across multiple messages within the same session.

        Args:
            session_id: Unique identifier for the conversation session
            filter_value: Format filter (e.g., "standard") or None to clear
        """
        if filter_value is None:
            self._format_filters.pop(session_id, None)
        else:
            self._format_filters[session_id] = filter_value

    def clear_format_filter(self, session_id: str) -> None:
        """Clear format filter preference for a session.

        Removes the format filter preference for the session without affecting
        conversation history. Safe to call even if the session doesn't exist.

        Args:
            session_id: Unique identifier for the conversation session
        """
        self._format_filters.pop(session_id, None)

    def get_games_filter(self, session_id: str) -> GamesFilter:
        """Retrieve games filter preference for a session.

        Args:
            session_id: Unique identifier for the conversation session

        Returns:
            Games filter (e.g., ["arena"]) or None if no filter is set
        """
        return self._games_filters.get(session_id, None)

    def set_games_filter(self, session_id: str, filter_value: GamesFilter) -> None:
        """Set games filter preference for a session.

        Stores the games filter preference for the session. This allows games
        filters to persist across multiple messages within the same session.

        Args:
            session_id: Unique identifier for the conversation session
            filter_value: Games filter (e.g., ["arena"]) or None to clear
        """
        if filter_value is None or (isinstance(filter_value, list) and len(filter_value) == 0):
            self._games_filters.pop(session_id, None)
        else:
            self._games_filters[session_id] = filter_value

    def clear_games_filter(self, session_id: str) -> None:
        """Clear games filter preference for a session.

        Removes the games filter preference for the session without affecting
        conversation history. Safe to call even if the session doesn't exist.

        Args:
            session_id: Unique identifier for the conversation session
        """
        self._games_filters.pop(session_id, None)

    def get_active_deck_id(self, session_id: str) -> str | None:
        """Retrieve active deck ID for a session.

        Args:
            session_id: Unique identifier for the conversation session

        Returns:
            Active deck ID (UUID string) or None if no deck is active
        """
        deck_id = self._active_deck_ids.get(session_id, None)
        logger.debug(
            "SessionManager.get_active_deck_id: session_id=%s, deck_id=%s, total_sessions=%d",
            session_id,
            deck_id,
            len(self._active_deck_ids),
        )
        return deck_id

    def set_active_deck_id(self, session_id: str, deck_id: str) -> None:
        """Set active deck ID for a session.

        Stores the active deck ID for the session. This allows the active
        deck to persist across multiple messages within the same session.

        Args:
            session_id: Unique identifier for the conversation session
            deck_id: Deck ID (UUID string) to set as active
        """
        self._active_deck_ids[session_id] = deck_id
        logger.info(
            "SessionManager.set_active_deck_id: session_id=%s, deck_id=%s, total_sessions=%d",
            session_id,
            deck_id,
            len(self._active_deck_ids),
        )

    def clear_active_deck_id(self, session_id: str) -> None:
        """Clear active deck ID for a session.

        Removes the active deck ID for the session without affecting
        conversation history or other session state. Safe to call even
        if the session doesn't exist.

        Args:
            session_id: Unique identifier for the conversation session
        """
        old_deck_id = self._active_deck_ids.pop(session_id, None)
        logger.info(
            "clear_active_deck_id: session=%s, cleared=%s, total_sessions=%d",
            session_id,
            old_deck_id,
            len(self._active_deck_ids),
        )

    def get_preference(self, session_id: str, preference_name: str, default: bool = True) -> bool:
        """Retrieve a boolean preference for a session.

        Args:
            session_id: Unique identifier for the conversation session
            preference_name: Name of the preference (e.g., "auto_feedback_enabled")
            default: Default value if preference not set

        Returns:
            Preference value or default if not set
        """
        session_prefs = self._preferences.get(session_id, {})
        return session_prefs.get(preference_name, default)

    def set_preference(self, session_id: str, preference_name: str, value: bool) -> None:
        """Set a boolean preference for a session.

        Args:
            session_id: Unique identifier for the conversation session
            preference_name: Name of the preference (e.g., "auto_feedback_enabled")
            value: Preference value to set
        """
        if session_id not in self._preferences:
            self._preferences[session_id] = {}
        self._preferences[session_id][preference_name] = value

    def get_search_context(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve search context for pagination.

        Args:
            session_id: Unique identifier for the conversation session

        Returns:
            Search context dictionary or None if not set
        """
        return self._search_contexts.get(session_id)

    def set_search_context(self, session_id: str, context: dict[str, Any]) -> None:
        """Store search context for pagination.

        Args:
            session_id: Unique identifier for the conversation session
            context: Search context containing filters and pagination parameters
        """
        self._search_contexts[session_id] = context


# Global session manager instance
_session_manager = ConversationSessionManager()


# Initialize observability (runs once at module import)
# Load config and configure Logfire if enabled
try:
    _config = AgentConfig()
    configure_observability(_config)
except Exception as e:
    # If config loading fails, log error but continue
    # This allows the module to be imported even if .env is missing
    logger.debug(f"Could not initialize observability: {e}")


# System prompt defining the agent's personality and role
SYSTEM_PROMPT = """You are Artificial-Planeswalker, an expert Magic: The Gathering \
deck building assistant.

CRITICAL OUTPUT FORMATTING RULE (THIS IS MANDATORY):
ALL tools that return card information include special HTML formatting for visual features. \
You MUST copy the ENTIRE tool output EXACTLY as-is into your response. This is TRUSTED HTML \
that you should pass through WITHOUT escaping, quoting, or modifying. Do NOT summarize, \
paraphrase, rewrite, clean up, escape HTML entities, or describe cards in your own words - \
paste the tool output directly with all HTML tags, symbols, and formatting preserved \
character-for-character. The HTML tags like <span> and <strong> are intentional and must \
appear in your response exactly as provided by the tool.

This applies to ALL card-related tools:
- lookup_card_by_name → copy the formatted output exactly
- search_cards_advanced → copy the entire numbered list exactly
- view_deck → copy the deck listing exactly
- ANY tool that returns card information → copy it exactly

Example (lookup_card_by_name):
Tool returns: "<strong><span class=\"card-hover\" ...>Lightning Bolt</span></strong> {R}..."
Your response: "Here's what I found:\\n\\n<strong><span class=\"card-hover\" \
...>Lightning Bolt</span></strong> {R}..."
NOT: "I found Lightning Bolt, a red instant..." ← This breaks all formatting!

Example (search_cards_advanced):
Tool returns: "Found 5 cards:\\n\\n1. <strong><span ...>Card One</span></strong> {1}{R}..."
Your response: "Found 5 cards:\\n\\n1. <strong><span ...>Card One</span></strong> {1}{R}..."
NOT: "I found 5 cards: Card One, Card Two..." ← This strips the formatting!

You can add brief commentary before or after the formatted output, but NEVER replace it.

CONTEXT-AWARE BEHAVIOR:
When users ask about cards by name and there's an active deck loaded, use that deck context \
to disambiguate which card they mean, then call the lookup tool with the exact card name. \
For example:
- If user has "Tinybones Archon" deck loaded and asks "tell me about tinybones", they're \
  asking about "Tinybones, the Pickpocket" from their deck
- Check the active deck cards to identify the specific card, then call lookup_card_by_name \
  with the full card name to get formatted details and images
- Only ask for clarification if the deck context doesn't resolve the ambiguity

TOOL USAGE RULES:
1. ALWAYS use tools for card information (never from memory)
2. ALWAYS copy tool outputs exactly with all HTML/formatting intact
3. Your commentary can frame the output but must not replace it
4. NEVER autonomously add cards to decks - ONLY add cards when the user explicitly requests it

DECK OPERATION RULES (CRITICAL):
5. When user asks to add cards:
   a. ALWAYS call add_card_to_deck tool FIRST
   b. If tool returns "No active deck", THEN create a new deck
   c. NEVER decide to create a deck without attempting add_card_to_deck first
   d. Trust the tool's error message over your assumptions about deck state

6. When user asks to create a deck:
   a. ALWAYS call create_deck tool explicitly
   b. Do NOT infer deck creation from "add card" requests
   c. Creating a deck requires explicit user intent

CRITICAL BEHAVIORAL CONSTRAINT:
You MUST NEVER call the add_card_to_deck tool unless the user has EXPLICITLY requested to add \
a specific card in their current message. Mana curve feedback and deck analysis are purely \
OBSERVATIONAL - they describe the current state and potential improvements, but you should \
NEVER take action on these observations without explicit user instruction.

Examples of explicit user requests (OK to add cards):
- "Add Lightning Bolt to my deck"
- "Put 4 copies of Sheoldred in the deck"
- "I want to add some removal spells"

Examples of observational feedback (DO NOT add cards):
- Tool output: "Deck has very few early plays (15% at ≤ 2 mana)"
  → Your response: Acknowledge the observation, do NOT search for or add low-cost cards
- Tool output: "Deck is becoming top-heavy (40% at 5+ mana)"
  → Your response: Acknowledge the observation, do NOT search for or add cheaper cards
- Tool output: "More 1-3 mana plays would improve early-game consistency"
  → Your response: Acknowledge the observation, do NOT search for or add cards

If you receive feedback suggesting deck improvements, you may:
- Acknowledge the feedback
- Explain what it means
- ASK the user if they want help finding cards to address the issue

But you must NEVER proactively search for or add cards without explicit user permission.

Your role is to help players:
- Find and lookup MTG cards using natural language queries
- Build Standard format decks with informed suggestions (when asked)
- Analyze mana curves and deck composition
- Identify synergies and strategic opportunities
- Validate deck construction rules

Always prioritize Standard format legality unless explicitly asked otherwise."""


def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    """History processor to limit message history size.

    Keeps only the most recent messages to prevent unbounded memory growth
    and token usage. Preserves system messages even when truncating to maintain
    consistent agent behavior.

    Strategy:
    - Keep last 10 messages (approximately 5 user-agent exchanges)
    - Always preserve system messages regardless of position
    - Token budget: ~2,000-10,000 tokens (well under 200k context window)
    - PydanticAI automatically maintains tool call/return pairing

    Args:
        messages: Complete conversation history

    Returns:
        Truncated message history with recent messages and system messages
    """
    # Return all messages if under limit
    if len(messages) <= 10:
        return messages

    # Separate system messages from other messages
    # System messages are ModelRequest with SystemPromptPart
    def is_system_message(msg: ModelMessage) -> bool:
        return isinstance(msg, ModelRequest) and any(
            isinstance(part, SystemPromptPart) for part in msg.parts
        )

    system_messages = [msg for msg in messages if is_system_message(msg)]
    non_system_messages = [msg for msg in messages if not is_system_message(msg)]

    # Keep last 10 non-system messages
    recent_messages = non_system_messages[-10:]

    # Combine: system messages first, then recent messages
    # This ensures the agent's personality and instructions remain consistent
    return system_messages + recent_messages


def _is_claude_model(model_name: str) -> bool:
    """Check if a model name refers to a Claude model.

    Args:
        model_name: Model identifier (e.g., "claude-sonnet-4.5" or "anthropic/claude-sonnet-4.5")

    Returns:
        True if the model is a Claude model, False otherwise
    """
    return "claude" in model_name.lower()


def _normalize_model_name(model_name: str, use_anthropic: bool) -> str:
    """Normalize model name for the selected provider.

    Anthropic models need the "anthropic/" prefix removed when using the native
    Anthropic provider, but OpenRouter requires the prefix.

    Args:
        model_name: Model identifier from configuration
        use_anthropic: Whether Anthropic provider will be used

    Returns:
        Normalized model name appropriate for the provider
    """
    # Remove "anthropic/" prefix for native Anthropic provider
    if use_anthropic and model_name.startswith("anthropic/"):
        return model_name.replace("anthropic/", "", 1)
    # Add "anthropic/" prefix for OpenRouter if missing and it's a Claude model
    elif not use_anthropic and _is_claude_model(model_name) and "/" not in model_name:
        return f"anthropic/{model_name}"
    return model_name


def _determine_provider(config: AgentConfig) -> tuple[bool, str]:
    """Determine which provider to use based on configuration and model.

    Provider selection logic:
    1. For Claude models: Prefer Anthropic API if anthropic_api_key is set
    2. For non-Claude models: Use OpenRouter API if openrouter_api_key is set
    3. Raise error if no suitable API key is available

    Args:
        config: Agent configuration with API keys and model name

    Returns:
        Tuple of (use_anthropic, normalized_model_name)

    Raises:
        AuthenticationError: If no suitable API key is available for the model
    """
    is_claude = _is_claude_model(config.agent_model)

    # Claude model with Anthropic API key available
    if is_claude and config.anthropic_api_key:
        normalized_model = _normalize_model_name(config.agent_model, use_anthropic=True)
        logger.info(
            f"Using Anthropic provider for Claude model: {normalized_model} "
            f"(original: {config.agent_model})"
        )
        return True, normalized_model

    # Claude model with only OpenRouter API key available
    if is_claude and config.openrouter_api_key:
        normalized_model = _normalize_model_name(config.agent_model, use_anthropic=False)
        logger.info(
            f"Using OpenRouter provider for Claude model: {normalized_model} "
            f"(original: {config.agent_model})"
        )
        return False, normalized_model

    # Non-Claude model with OpenRouter API key available
    if not is_claude and config.openrouter_api_key:
        normalized_model = _normalize_model_name(config.agent_model, use_anthropic=False)
        logger.info(f"Using OpenRouter provider for non-Claude model: {normalized_model}")
        return False, normalized_model

    # No suitable API key available
    if is_claude:
        raise AuthenticationError(
            details={
                "error": f"Claude model '{config.agent_model}' requires ANTHROPIC_API_KEY or "
                "OPENROUTER_API_KEY"
            }
        )
    else:
        raise AuthenticationError(
            details={
                "error": f"Non-Claude model '{config.agent_model}' requires OPENROUTER_API_KEY"
            }
        )


def create_agent(
    config: AgentConfig | None = None,
    defer_model_check: bool = False,
) -> Agent[AgentDependencies, str]:
    """Create a PydanticAI agent configured with Anthropic or OpenRouter.

    This factory function initializes an agent with the specified configuration,
    automatically selecting the appropriate provider:
    - Anthropic API for Claude models (when ANTHROPIC_API_KEY is available)
    - OpenRouter API for non-Claude models or as fallback

    Args:
        config: Agent configuration. If None, loads from environment variables.
        defer_model_check: If True, skip immediate model validation (useful for testing).

    Returns:
        Configured PydanticAI agent instance

    Raises:
        AuthenticationError: If no suitable API key is available
        ValueError: If configuration is invalid

    Example:
        >>> # Using Anthropic API for Claude
        >>> config = AgentConfig(
        ...     anthropic_api_key="sk-ant-...",
        ...     agent_model="claude-sonnet-4.5"
        ... )
        >>> agent = create_agent(config)
        >>> result = await agent.run("Show me Lightning Bolt")
        >>>
        >>> # Using OpenRouter for GPT
        >>> config = AgentConfig(
        ...     openrouter_api_key="sk-or-...",
        ...     agent_model="openai/gpt-4"
        ... )
        >>> agent = create_agent(config)
    """
    # Load configuration from environment if not provided
    if config is None:
        try:
            config = AgentConfig()
        except Exception as e:
            raise AuthenticationError(details={"error": str(e)}) from e

    # Determine which provider to use and normalize model name
    use_anthropic, normalized_model = _determine_provider(config)

    # Create the appropriate model instance
    model: AnthropicModel | OpenAIChatModel
    if use_anthropic:
        # Use native Anthropic provider
        anthropic_provider = AnthropicProvider(
            api_key=config.anthropic_api_key,
        )
        model = AnthropicModel(
            model_name=normalized_model,
            provider=anthropic_provider,
        )
    else:
        # Use OpenRouter provider
        openrouter_provider = OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key,
        )
        model = OpenAIChatModel(
            model_name=normalized_model,
            provider=openrouter_provider,
        )

    # Configure model settings based on provider
    # Anthropic has restrictions on sampling parameters, so only pass max_tokens
    if use_anthropic:
        model_settings = ModelSettings(
            max_tokens=config.agent_max_tokens,
        )
    else:
        model_settings = ModelSettings(
            temperature=config.agent_temperature,
            max_tokens=config.agent_max_tokens,
            top_p=config.agent_top_p,
        )

    # Create agent with model, settings, dependency type, and history processor
    agent: Agent[AgentDependencies, str] = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        model_settings=model_settings,
        deps_type=AgentDependencies,
        defer_model_check=defer_model_check,
        history_processors=[keep_recent_messages],
    )

    # Register tools
    # Import here to avoid circular dependencies
    from .tools.bug_report import report_bug
    from .tools.card_lookup import lookup_card_by_name
    from .tools.card_search import search_cards_advanced
    from .tools.deck_tools import (
        add_card_to_deck,
        create_deck,
        delete_deck,
        list_decks,
        load_deck,
        remove_card_from_deck,
        update_card_quantity,
        update_deck_strategy,
        view_deck,
    )
    from .tools.format_filter import set_format_filter
    from .tools.games_filter import set_games_filter
    from .tools.mana_curve import analyze_deck_mana_curve
    from .tools.preferences import toggle_auto_feedback
    from .tools.synergy_detection import detect_deck_synergies
    from .tools.synergy_suggestions import suggest_synergy_cards

    # Tools are automatically registered via decorator when function is defined
    # We just need to reference them to ensure they're loaded
    agent.tool(lookup_card_by_name)
    agent.tool(search_cards_advanced)
    agent.tool(set_format_filter)
    agent.tool(set_games_filter)
    agent.tool(report_bug)
    agent.tool(create_deck)
    agent.tool(add_card_to_deck)
    agent.tool(view_deck)
    agent.tool(remove_card_from_deck)
    agent.tool(update_card_quantity)
    agent.tool(update_deck_strategy)
    agent.tool(list_decks)
    agent.tool(load_deck)
    agent.tool(delete_deck)
    agent.tool(analyze_deck_mana_curve)
    agent.tool(toggle_auto_feedback)
    agent.tool(detect_deck_synergies)
    agent.tool(suggest_synergy_cards)

    return agent


def _build_deck_context_message(deck: Any) -> str:
    """Build system message describing active deck state.

    Returns concise, high-signal context that prevents agent confusion
    about the current active deck.

    Args:
        deck: Active deck object with id, name, format, and deck_cards attributes

    Returns:
        Formatted system message string with deck context
    """
    card_count = len(deck.deck_cards)
    deck_id_short = deck.id[:8]

    return (
        f"ACTIVE DECK CONTEXT:\n"
        f'- You currently have a deck loaded: "{deck.name}" (ID: {deck_id_short}...)\n'
        f"- Format: {deck.format}\n"
        f"- Cards: {card_count} cards currently in deck\n"
        f"- ALWAYS add cards to this deck unless user explicitly requests a new deck\n"
        f"- If user says 'add [card]', use add_card_to_deck tool on THIS deck"
    )


def _inject_system_context(
    history: list[ModelMessage],
    context: str,
) -> list[ModelMessage]:
    """Inject deck context into conversation history as system message.

    Strategy: Prepend to most recent system message, or create new one.
    System messages have highest attention weight in LLM processing.

    Args:
        history: Complete conversation history
        context: System context string to inject

    Returns:
        Updated message history with injected context
    """
    # Find last system message
    for i in range(len(history) - 1, -1, -1):
        if isinstance(history[i], ModelRequest):
            # Check if this is a system message
            for part in history[i].parts:
                if isinstance(part, SystemPromptPart):
                    # Prepend context to existing system message
                    existing_content = part.content
                    part.content = f"{context}\n\n{existing_content}"
                    logger.debug(
                        "Injected deck context into existing system message at index %d", i
                    )
                    return history

    # No system message found - inject new one at start
    logger.debug("No system message found, creating new one with deck context")
    system_request = ModelRequest(parts=[SystemPromptPart(content=context)])
    return [system_request, *history]


async def run_agent_with_session(  # type: ignore[no-untyped-def]
    user_input: str,
    session_id: str,
    deps: AgentDependencies,
    agent: Agent[AgentDependencies, str] | None = None,
):
    """Run the agent with automatic session history management.

    This helper function provides transparent conversation context by managing
    message history through the session manager. It handles history retrieval,
    agent invocation, message extraction, and history updates automatically.

    The UI layer only needs to provide user input and session ID - all message
    history management is handled transparently by the agent layer.

    Args:
        user_input: User's message/query
        session_id: Unique session identifier (e.g., from Chainlit)
        deps: Agent dependencies (repositories, etc.)
        agent: Optional agent instance. If None, creates default agent.

    Returns:
        The complete RunResult object containing:
        - output: Agent's text response (str)
        - all_messages(): Complete message history including tool calls

    Example:
        >>> from legacy.agent import run_agent_with_session
        >>> deps = AgentDependencies(card_repo=repo)
        >>> result = await run_agent_with_session(
        ...     user_input="Tell me about Lightning Bolt",
        ...     session_id="session-123",
        ...     deps=deps
        ... )
        >>> print(result.output)  # Get response text
        >>> messages = result.all_messages()  # Get full message history
    """
    # Create agent if not provided
    if agent is None:
        agent = create_agent()

    # Retrieve conversation history for this session
    history = _session_manager.get_history(session_id)

    # Inject active deck context into system message if deck is active
    if deps.active_deck:
        deck_context = _build_deck_context_message(deps.active_deck)
        history = _inject_system_context(history, deck_context)
        logger.info(
            "Injected active deck context for deck '%s' (ID: %s...)",
            deps.active_deck.name,
            deps.active_deck.id[:8],
        )

    # Run agent with message history
    result = await agent.run(user_input, deps=deps, message_history=history)

    # Extract all messages from the result (includes user prompt, tool calls, responses)
    all_messages = result.all_messages()

    # Update session manager with complete message history
    _session_manager.update_history(session_id, all_messages)

    # Return the complete result object (UI layer can access .output and .all_messages())
    return result

"""Chainlit application entry point for Artificial-Planeswalker.

This module defines the Chainlit chat interface handlers for user interaction.
It serves as the UI layer, which delegates all business logic to the agent layer.

Usage:
    uv run chainlit run src/ui/app.py

Architecture Note:
    The UI layer must NOT import database models or repositories directly.
    All data access should flow through the agent layer for proper separation.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import chainlit as cl
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# Import action callback modules to register callbacks
# These imports have side effects (decorator registration) and must not be removed
import src.ui.actions.card_actions  # noqa: F401
import src.ui.actions.deck_actions  # noqa: F401
import src.ui.actions.filter_actions  # noqa: F401
import src.ui.actions.pagination_actions  # noqa: F401
from src.agent.core import _session_manager, create_agent
from src.agent.dependencies import AgentDependencies
from src.agent.errors import AuthenticationError
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from src.ui.action_callbacks import store_action_message
from src.ui.components.sidebar import update_deck_sidebar
from src.ui.handlers.message_handler import handle_user_message

# Configure logging
logger = logging.getLogger(__name__)

# Global state for database and agent
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_agent: Agent[AgentDependencies, str] | None = None


async def initialize_app() -> None:
    """Initialize database and agent on first use.

    This function is idempotent and can be safely called multiple times.
    It sets up the global database engine, session factory, and agent instance.
    """
    global _engine, _session_factory, _agent

    if _engine is not None:
        return  # Already initialized

    logger.info("Initializing Artificial-Planeswalker application...")

    try:
        # Create database engine and initialize schema
        _engine = create_engine()
        await init_database(_engine)
        _session_factory = create_session_factory(_engine)
        logger.info("Database initialized successfully")

        # Create agent
        _agent = create_agent()
        logger.info("Agent initialized successfully")

        # Initialize symbol cache for visual mana symbols
        from src.ui.symbols import get_symbol_cache

        try:
            await get_symbol_cache()
            logger.info("Symbol cache initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize symbol cache: {e}")
            logger.warning("Visual mana symbols will fall back to text notation")

    except AuthenticationError as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


def detect_disambiguation_context(user_message: str) -> str:
    """Detect user intent (view vs add) from message for disambiguation context.

    Analyzes the user's message for keywords indicating whether they want to
    view card details or add a card to their deck.

    Args:
        user_message: The user's message text

    Returns:
        "add" if add intent detected, "view" otherwise (default)

    Examples:
        >>> detect_disambiguation_context("add bolt to deck")
        "add"
        >>> detect_disambiguation_context("show me bolt")
        "view"
    """
    message_lower = user_message.lower()

    # Add intent keywords
    add_keywords = ["add", "include", "put in", "put into"]
    if any(keyword in message_lower for keyword in add_keywords):
        return "add"

    # Default to view (safer, non-destructive)
    return "view"


async def update_deck_sidebar_wrapper(session_id: str) -> None:
    """Wrapper for update_deck_sidebar that provides the session factory.

    This wrapper is used by action callbacks and other parts of app.py that need
    to update the sidebar without having direct access to _session_factory.

    Args:
        session_id: Current session ID for retrieving active deck
    """
    if _session_factory:
        await update_deck_sidebar(session_id, _session_factory)


@asynccontextmanager
async def get_agent_dependencies(session_id: str) -> AsyncGenerator[AgentDependencies, None]:
    """Create AgentDependencies for a single request with session-aware state.

    This context manager creates a database session and repositories for each
    agent invocation, and retrieves session state (e.g., format filter, active
    deck) from the session manager. The active deck is loaded once per request
    and cached in dependencies for all tools in the same agent run.

    Transaction Safety: Ensures clean session state on entry and performs rollback
    on errors to prevent session contamination across tool calls.

    Args:
        session_id: Unique session identifier for state restoration

    Yields:
        AgentDependencies with repositories, cached active deck, and session state
    """
    # Auto-initialize if not already initialized (defensive programming for action callbacks)
    if _session_factory is None:
        logger.warning("Application not initialized, auto-initializing...")
        await initialize_app()

    # Type assertion: _session_factory is guaranteed to be non-None after initialize_app()
    assert _session_factory is not None, "Failed to initialize session factory"

    # Retrieve session state from session manager
    format_filter = _session_manager.get_format_filter(session_id)
    active_deck_id = _session_manager.get_active_deck_id(session_id)

    logger.info(
        "get_agent_dependencies: session_id=%s, format_filter=%s, active_deck_id=%s",
        session_id,
        format_filter,
        active_deck_id,
    )

    async with _session_factory() as session:
        try:
            # Ensure clean session state before tool execution
            # If session has a rolled-back transaction from a previous error, clear it
            if session.in_transaction():
                logger.warning(
                    "Session %s entered with active transaction, rolling back", session_id
                )
                await session.rollback()

            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Load active deck once per request (if deck ID exists)
            active_deck = None
            if active_deck_id:
                active_deck = await deck_repository.get_deck_with_cards(active_deck_id)
                if active_deck is None:
                    # Defensive: deck was deleted, clear the stale ID from session
                    logger.warning(
                        "Active deck %s for session %s not found, clearing stale ID",
                        active_deck_id,
                        session_id,
                    )
                    _session_manager.clear_active_deck_id(session_id)

            logger.info(
                "Created deps: session=%s, deck=%s, name=%s, format=%s",
                session_id,
                active_deck_id,
                active_deck.name if active_deck else None,
                format_filter,
            )

            yield AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=_session_manager,
                format_filter=format_filter,
                active_deck=active_deck,
            )

        except Exception as e:
            # Rollback on any error during tool execution to clean up session state
            logger.error(
                "Error during agent execution for session %s, rolling back session: %s",
                session_id,
                str(e),
            )
            await session.rollback()
            raise


@cl.on_chat_start
async def on_chat_start() -> None:
    """Handle chat session initialization.

    Displays a welcome message when a new chat session begins and initializes
    the application if needed. Also initializes the deck sidebar state.
    """
    # Initialize application on first chat
    try:
        await initialize_app()
    except AuthenticationError:
        error_message = """# Configuration Error

I couldn't start because the OpenRouter API key is missing or invalid.

Please set the `OPENROUTER_API_KEY` environment variable in your `.env` file.

You can get an API key from: https://openrouter.ai/keys
"""
        await cl.Message(content=error_message).send()
        return
    except Exception as e:
        logger.exception("Failed to initialize application")
        error_message = f"""# Initialization Error

Something went wrong while starting up:

```
{str(e)}
```

Please check the logs for more details.
"""
        await cl.Message(content=error_message).send()
        return

    welcome_message = """# Welcome to Artificial-Planeswalker!

I'm your AI-powered Magic: The Gathering deck-building assistant. I can help you:

- **Look up cards** by name or criteria
- **Search for cards** by color, type, mana cost, and abilities
- **Filter by format** (Standard support included)
- **Analyze card details** including mana cost, type, and abilities

All card data is stored locally for fast, offline-friendly access.

Try asking me something like:
- "Show me Lightning Bolt"
- "Find red creatures with haste under 4 mana"
- "Only show me Standard-legal cards"

Let's build something great!
"""

    await cl.Message(content=welcome_message).send()

    # Display format selection buttons
    format_selection_content = """**Choose a format filter:**

Filtering cards by format will limit search results to cards legal in that format."""

    format_actions = [
        cl.Action(
            name="set_format_filter",
            payload={"format": "standard"},
            label="⚡ Standard",
            tooltip="Show only Standard-legal cards",
        ),
        cl.Action(
            name="set_format_filter",
            payload={"format": "all"},
            label="🌐 All Formats",
            tooltip="Show cards from all formats",
        ),
    ]

    format_message = cl.Message(content=format_selection_content, actions=format_actions)
    await format_message.send()

    # Store format selection message for later removal
    store_action_message("format_selection_message", format_message)

    # Display games platform selection buttons
    games_selection_content = """**Choose a platform filter:**

Filtering by platform will show only cards available on the selected platform(s)."""

    games_actions = [
        cl.Action(
            name="set_games_filter",
            payload={"games": "arena"},
            label="💻 Arena",
            tooltip="Show only MTG Arena cards",
        ),
        cl.Action(
            name="set_games_filter",
            payload={"games": "paper"},
            label="📖 Paper",
            tooltip="Show only paper Magic cards",
        ),
        cl.Action(
            name="set_games_filter",
            payload={"games": "mtgo"},
            label="🖥️ MTGO",
            tooltip="Show only Magic Online cards",
        ),
        cl.Action(
            name="set_games_filter",
            payload={"games": "all"},
            label="🌐 All Platforms",
            tooltip="Show cards from all platforms",
        ),
    ]

    games_message = cl.Message(content=games_selection_content, actions=games_actions)
    await games_message.send()

    # Store games selection message for later removal
    store_action_message("games_selection_message", games_message)

    # Initialize sidebar state (will be empty if no active deck)
    session_id = cl.user_session.get("id")
    if session_id:
        await update_deck_sidebar_wrapper(session_id)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle incoming user messages by delegating to message handler.

    This function serves as the Chainlit lifecycle hook for message handling.
    All orchestration logic is delegated to the message_handler module.

    Args:
        message: The incoming message from the user.
    """
    if _agent is None:
        await cl.Message(content="Error: Agent not initialized. Please refresh the page.").send()
        return

    # Get session ID from Chainlit for conversation history tracking
    session_id = cl.user_session.get("id")
    if session_id is None:
        logger.warning("No session ID found, using default")
        session_id = "default"

    # Get agent dependencies with database session and restored session state
    async with get_agent_dependencies(session_id) as deps:
        # Delegate to message handler for orchestration
        await handle_user_message(
            message=message,
            agent=_agent,
            session_id=session_id,
            deps=deps,
            update_sidebar_callback=update_deck_sidebar_wrapper,
        )

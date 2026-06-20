"""Agent dependencies for dependency injection into PydanticAI tools.

This module defines the dependencies that are injected into agent tools via
PydanticAI's RunContext. This enables type-safe access to repositories and
other services within tool implementations, while also facilitating testing
through dependency mocking.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.data.repositories.card import CardRepository, FormatFilter, GamesFilter
from src.data.repositories.deck import DeckRepository
from src.data.schemas.deck import Deck

if TYPE_CHECKING:
    from legacy.agent.core import ConversationSessionManager


@dataclass
class AgentDependencies:
    """Dependencies injected into agent tools via RunContext.

    This dataclass holds all repository instances and services that agent
    tools need to access. Tools receive dependencies through the RunContext
    parameter.

    Attributes:
        card_repository: Repository for querying card data from the database.
            Used by card lookup tools to search for cards by name, color, type, etc.
        deck_repository: Repository for deck-related database operations.
            Used by deck tools to create, update, and manage decks.
        session_id: Unique identifier for the current conversation session.
            Used by tools to persist session state (e.g., format filter preferences)
            to the session manager. Required for state persistence across messages.
        _session_manager: Private reference to ConversationSessionManager for
            session state persistence (format filter, active deck ID).
        format_filter: Current format filter setting for card queries.
            None means no filtering (show all cards regardless of format).
            "standard" filters to only show Standard-legal cards.
            This setting persists across tool invocations within the same session.
        games_filter: Current games availability filter for card queries.
            None means no filtering (show all cards regardless of platform).
            ["arena"] filters to only show Arena-available cards.
            This setting persists across tool invocations within the same session.
        active_deck: Cached Deck object loaded at dependency creation time.
            None if no deck is active or deck was deleted. This deck is loaded
            once per request from the database (including all cards) and cached
            for all tools in the same agent run. Tools can access deck properties
            (ID, name, format, cards) directly without additional database queries.
        ui_elements: List to collect UI elements (e.g., images) during tool execution.
            Tools can append Chainlit elements here, and the UI layer will attach
            them to the response message. Cleared at the start of each agent run.
        sidebar_needs_update: Flag indicating sidebar should be updated after tool execution.
            Tools set this to True when they modify deck state (create, load, delete).
            The UI layer checks this flag and updates the sidebar accordingly.
        auto_feedback_enabled: Property for session-level auto-feedback preference.
            Defaults to True (opt-out model). Users can disable via toggle_auto_feedback tool.
            Persists across messages in the same session via ConversationSessionManager.

    Example:
        ```python
        from pydantic_ai import Agent, RunContext

        @agent.tool
        async def add_card_to_deck(
            ctx: RunContext[AgentDependencies],
            card_name: str,
            quantity: int
        ) -> str:
            # Check if deck is active (single null check)
            if ctx.deps.active_deck is None:
                return "No active deck. Please create or load a deck first."

            # Access cached deck directly - no database query needed
            deck = ctx.deps.active_deck
            card = await ctx.deps.card_repository.find_by_name_exact(card_name)

            # Modify deck...
            return f"Added {quantity}x {card_name} to {deck.name}"
        ```

    Notes:
        - Future repositories and services should be added as new attributes
          (e.g., synergy_engine, format_validator)
        - All repositories should be async-compatible
        - Dependencies are created per agent run, not per agent instance
        - format_filter is mutable session state that persists across tool
          invocations within the same session
        - active_deck is loaded once at dependency creation and cached for
          the duration of the request. If deck state changes during the run,
          tools should reload from repository or complete the request.
        - session_id enables session state persistence via the session manager
    """

    card_repository: CardRepository
    deck_repository: DeckRepository
    session_id: str
    _session_manager: "ConversationSessionManager"
    format_filter: FormatFilter = field(default=None)
    games_filter: GamesFilter = field(default=None)
    active_deck: Deck | None = field(default=None)
    ui_elements: list[Any] = field(default_factory=list)
    sidebar_needs_update: bool = field(default=False)

    @property
    def auto_feedback_enabled(self) -> bool:
        """Check if automatic curve feedback is enabled for this session.

        Returns:
            True if auto-feedback enabled (default), False if disabled by user
        """
        return self._session_manager.get_preference(
            self.session_id, "auto_feedback_enabled", default=True
        )

    def set_auto_feedback_enabled(self, enabled: bool) -> None:
        """Set automatic curve feedback preference for this session.

        Args:
            enabled: True to enable auto-feedback, False to disable
        """
        self._session_manager.set_preference(self.session_id, "auto_feedback_enabled", enabled)

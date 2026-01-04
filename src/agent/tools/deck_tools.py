"""Deck management tools for PydanticAI agent.

This module provides tools for creating and managing Magic: The Gathering decks
through natural language conversation. Tools handle deck creation, modification,
and state management via the session manager.
"""

from typing import Any

from pydantic_ai import RunContext
from sqlalchemy.exc import IntegrityError

from src.agent.core import _session_manager
from src.agent.dependencies import AgentDependencies
from src.logic import validate_card_addition


async def create_deck(
    ctx: RunContext[AgentDependencies],
    name: str,
    format: str = "standard",
    strategy: str | None = None,
) -> str:
    """Create a new deck and set it as the active deck for the session.

    This tool creates a new deck with the specified name, format, and optional strategy,
    persists it to the database, and sets it as the active deck in the session context.
    The active deck ID will be available in subsequent tool invocations within
    the same session.

    Duplicate deck names are allowed since deck IDs are unique. If a deck with
    the same name already exists, a new deck with a unique ID will still be
    created.

    Args:
        ctx: PydanticAI run context with agent dependencies
        name: Deck name (user-provided via natural language)
        format: MTG format (e.g., "standard", "commander"). Defaults to "standard".
        strategy: Optional deck strategy description (e.g., "Fast aggro", "Control with card draw")

    Returns:
        User-friendly confirmation message with deck name and ID

    Examples:
        User: "create a new deck called Mono Red Aggro"
        Agent invokes: create_deck(ctx, name="Mono Red Aggro", format="standard")
        Returns: "Created deck 'Mono Red Aggro' (standard format) with ID: deck-123..."

        User: "create a control deck called Counter Magic with a strategy focused on counters"
        Agent invokes: create_deck(ctx, name="Counter Magic", format="standard",
                                   strategy="Control deck focused on counters and card draw")
        Returns: "Created deck 'Counter Magic' (standard format) with ID: deck-123...
                 Strategy: Control deck focused on counters and card draw..."

    Notes:
        - Duplicate names are allowed (IDs are unique)
        - Sets created deck as active via session manager
        - Strategy is optional and can be added/updated later
        - Returns error message if database operation fails
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        session_id = deps.session_id

        # Defensive: Ensure clean session state before database operations
        if deps.deck_repository.session.in_transaction():
            await deps.deck_repository.session.rollback()

        # Create deck via repository (with optional strategy)
        deck = await deps.deck_repository.create_deck(name=name, format=format, strategy=strategy)

        # Store deck ID as active deck in session manager
        _session_manager.set_active_deck_id(session_id, deck.id)

        # Update cached active deck in dependencies for current agent run
        # This ensures subsequent tools in the same turn see the new deck
        deps.active_deck = deck

        # Request sidebar update to show new active deck
        deps.sidebar_needs_update = True

        # Build confirmation message
        confirmation = f"Created deck '{deck.name}' ({deck.format} format) with ID: {deck.id}\n\n"

        # Add strategy info if provided
        if deck.strategy:
            confirmation += f"Strategy: {deck.strategy}\n\n"

        confirmation += (
            "This deck is now active and ready for card additions. "
            "All subsequent deck operations will apply to this deck unless you "
            "create or select a different deck."
        )

        return confirmation

    except Exception as e:
        # Handle database or other errors gracefully
        return (
            f"Failed to create deck '{name}'. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def add_card_to_deck(ctx: RunContext[AgentDependencies], name: str, quantity: int = 1) -> str:
    """Add cards to the active deck with quantity validation and deck construction rule enforcement.

    This tool adds a specified quantity of a card to the active deck while enforcing
    Standard format deck construction rules:
    - Maximum 4 copies of any non-basic land card
    - Basic lands are unlimited
    - All cards must be Standard-legal

    The tool handles card lookup, format legality checking, deck construction validation,
    and database updates. If the card already exists in the deck, the quantity is updated.

    Args:
        ctx: PydanticAI run context with agent dependencies
        name: Card name (user-provided via natural language)
        quantity: Number of copies to add (defaults to 1)

    Returns:
        User-friendly confirmation or error message

    Examples:
        User: "add 4 Lightning Bolt to my deck"
        Agent invokes: add_card_to_deck(ctx, name="Lightning Bolt", quantity=4)
        Returns: "Added 4 copies of 'Lightning Bolt'. Deck now has 4 copies (total: 61 cards)."

        User: "add Sheoldred to my deck"
        Agent invokes: add_card_to_deck(ctx, name="Sheoldred", quantity=1)
        Returns: "Added 1 copy of 'Sheoldred, the Apocalypse'. Deck now has 1 copy
                 (total: 62 cards)."

    Error Cases:
        - No active deck: "No active deck. Create a deck first with 'create a new deck'."
        - Card not found: "Card 'Lightningbolt' not found. Did you mean:
                          Lightning Bolt, Lightning Strike?"
        - Not Standard-legal: "'Sol Ring' is not legal in Standard format."
        - Exceeds 4-copy limit: "Cannot add 2 copies of 'Lightning Bolt'. Deck would have
                                5 copies (max 4 for non-basic lands)."

    Notes:
        - Requires active deck in session context
        - Validates Standard format legality
        - Enforces 4-copy limit (except basic lands - unlimited)
        - Updates existing card quantity if card already in deck
        - Returns clear error messages for all validation failures
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        deck = deps.active_deck

        # Log tool invocation with session/deck state
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            "add_card_to_deck: session_id=%s, card_name=%s, quantity=%d, active_deck=%s",
            deps.session_id,
            name,
            quantity,
            deck.name if deck else None,
        )

        # Defensive: Ensure clean session state before database operations
        # If a previous tool triggered a rollback, this clears the rolled-back state
        if deps.deck_repository.session.in_transaction():
            await deps.deck_repository.session.rollback()

        # Check if active deck exists
        if deck is None:
            logger.warning(
                "add_card_to_deck: No active deck for session_id=%s",
                deps.session_id,
            )
            return "No active deck. Create a deck first with 'create a new deck'."

        # Look up card by exact name (respects current format filter)
        card = await deps.card_repository.find_by_name_exact(name, format_filter=deps.format_filter)

        # If not found, try partial match for suggestions
        if card is None:
            suggestions = await deps.card_repository.find_by_name_partial(
                name, format_filter=deps.format_filter
            )
            if suggestions:
                suggestion_names = ", ".join([c.name for c in suggestions[:3]])
                return f"Card '{name}' not found. Did you mean: {suggestion_names}?"
            return f"Card '{name}' not found."

        # Validate Standard format legality
        if card.legalities.get("standard") != "legal":
            return f"'{card.name}' is not legal in Standard format."

        # Validate deck construction rules (4-copy limit, basic land exception)
        validation_result = validate_card_addition(deck, card, quantity)

        if not validation_result.is_valid:
            return validation_result.error_message or "Validation failed."

        # Check if card already exists in deck (mainboard)
        existing_card = next(
            (dc for dc in deck.deck_cards if dc.card_id == card.id and not dc.sideboard), None
        )

        if existing_card:
            # Update quantity
            new_quantity = existing_card.quantity + quantity
            await deps.deck_repository.update_card_quantity(
                deck_id=deck.id,
                card_id=card.id,
                quantity=new_quantity,
                sideboard=False,
            )
        else:
            # Add new card
            try:
                await deps.deck_repository.add_card_to_deck(
                    deck_id=deck.id,
                    card_id=card.id,
                    quantity=quantity,
                    sideboard=False,
                )
            except IntegrityError:
                # Card already exists in deck (UNIQUE constraint violation)
                # Repository has already rolled back the transaction
                return (
                    f"'{card.name}' is already in your deck. "
                    f"Use the update quantity command to modify the number of copies."
                )

        # Reload deck to get updated card count
        updated_deck = await deps.deck_repository.get_deck_with_cards(deck.id)

        if updated_deck is None:
            return "Failed to reload deck after adding card."

        # Calculate total card count in mainboard
        total_cards = sum(dc.quantity for dc in updated_deck.deck_cards if not dc.sideboard)

        # Get new total for this specific card
        card_total = sum(
            dc.quantity
            for dc in updated_deck.deck_cards
            if dc.card_id == card.id and not dc.sideboard
        )

        # Request sidebar update to show updated card count and colors
        deps.sidebar_needs_update = True

        # Build confirmation message
        confirmation = (
            f"Added {quantity} {'copy' if quantity == 1 else 'copies'} of '{card.name}'. "
            f"Deck now has {card_total} {'copy' if card_total == 1 else 'copies'} "
            f"(total: {total_cards} cards)."
        )

        # Generate automatic curve feedback if enabled
        if deps.auto_feedback_enabled:
            # Import here to avoid circular dependency at module level
            from src.logic.mana_curve import generate_contextual_feedback

            # Get all cards in deck for feedback analysis
            # Extract Card objects from DeckCard relationships
            deck_card_list = [dc.card for dc in updated_deck.deck_cards if not dc.sideboard]

            # Generate contextual feedback
            feedback = generate_contextual_feedback(deck_card_list, card)

            # Append feedback to confirmation if feedback should be displayed
            if feedback and feedback.should_display:
                confirmation += f"\n\n💡 **Curve Feedback**: {feedback.message}"

        # Return confirmation with optional feedback
        return confirmation

    except Exception as e:
        # Handle unexpected errors gracefully
        return (
            f"Failed to add card '{name}' to deck. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def view_deck(ctx: RunContext[AgentDependencies]) -> str:
    """View the current active deck contents with formatted card list and summary.

    This tool displays the active deck with all cards grouped by type (Creatures,
    Spells, Lands), sorted by mana cost within each group. Shows deck name, format,
    card counts, and legality status.

    Args:
        ctx: PydanticAI run context with agent dependencies

    Returns:
        Formatted deck list as markdown string, or error message if no active deck

    Example:
        User: "show my deck"
        Agent invokes: view_deck(ctx)
        Returns: Formatted markdown with deck name, cards grouped by type, summary

    Error Cases:
        - No active deck: "No active deck. Create a new deck or load an existing one..."
        - Empty deck: "Your deck is empty. Add cards to get started."
        - Database error: "Failed to load deck..."

    Notes:
        - Requires active deck in session context
        - Returns formatted markdown (UI-independent)
        - Shows both mainboard and sideboard
        - Includes legality indicator for Standard format
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        deck = deps.active_deck

        # Check if active deck exists
        if deck is None:
            return (
                "No active deck. Create a new deck or load an existing one to get started.\n\n"
                "Try saying: 'create a new deck called My Deck'"
            )

        # Import formatter here to avoid circular import at module level
        from src.ui.formatters import format_deck_for_display

        # Format deck for display
        formatted_deck = format_deck_for_display(deck)

        return formatted_deck

    except Exception as e:
        # Handle unexpected errors gracefully
        return (
            f"Failed to load deck. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def remove_card_from_deck(
    ctx: RunContext[AgentDependencies], card_name: str, sideboard: bool = False
) -> str:
    """Remove a card from the active deck (mainboard or sideboard).

    This tool removes all copies of a specified card from the active deck.
    Validates that the card exists in the deck before removal.

    Args:
        ctx: PydanticAI run context with agent dependencies
        card_name: Card name to remove (user-provided via natural language)
        sideboard: True to remove from sideboard, False for mainboard (default)

    Returns:
        User-friendly confirmation or error message

    Examples:
        User: "remove Lightning Bolt from my deck"
        Agent invokes: remove_card_from_deck(ctx, card_name="Lightning Bolt", sideboard=False)
        Returns: "Removed Lightning Bolt from your deck."

        User: "remove Rest in Peace from sideboard"
        Agent invokes: remove_card_from_deck(ctx, card_name="Rest in Peace", sideboard=True)
        Returns: "Removed Rest in Peace from sideboard."

    Error Cases:
        - No active deck: "No active deck. Create or load a deck first."
        - Card not found in database: "Card 'Xyz' not found in card database..."
        - Card not in deck: "'Lightning Bolt' not found in your deck..."

    Notes:
        - Requires active deck in session context
        - Removes ALL copies of the card from specified location
        - Provides suggestions if card name not found (partial match)
        - Returns clear error messages for all validation failures
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        deck = deps.active_deck

        # Defensive: Ensure clean session state before database operations
        if deps.deck_repository.session.in_transaction():
            await deps.deck_repository.session.rollback()

        # Check if active deck exists
        if deck is None:
            return "No active deck. Create or load a deck first."

        # Look up card by exact name
        card = await deps.card_repository.find_by_name_exact(
            card_name, format_filter=deps.format_filter
        )

        # If not found, try partial match for suggestions
        if card is None:
            suggestions = await deps.card_repository.find_by_name_partial(
                card_name, format_filter=deps.format_filter
            )
            if suggestions:
                suggestion_names = ", ".join([c.name for c in suggestions[:3]])
                return (
                    f"Card '{card_name}' not found in card database. "
                    f"Did you mean: {suggestion_names}?"
                )
            return (
                f"Card '{card_name}' not found in card database. Check spelling or use card search."
            )

        # Find card in deck
        deck_card = next(
            (dc for dc in deck.deck_cards if dc.card_id == card.id and dc.sideboard == sideboard),
            None,
        )

        if deck_card is None:
            location = "sideboard" if sideboard else "deck"
            return (
                f"'{card.name}' not found in your {location}. "
                f"Check the card name or view your deck to see current contents."
            )

        # Remove card from deck
        success = await deps.deck_repository.remove_card_from_deck(
            deck_id=deck.id,
            card_id=card.id,
            sideboard=sideboard,
        )

        if success:
            location = "sideboard" if sideboard else "deck"
            return f"Removed '{card.name}' from your {location}."
        else:
            return f"Failed to remove '{card.name}' from deck. Please try again."

    except Exception as e:
        # Handle unexpected errors gracefully
        return (
            f"Failed to remove card '{card_name}' from deck. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def update_card_quantity(
    ctx: RunContext[AgentDependencies],
    card_name: str,
    quantity: int,
    sideboard: bool = False,
) -> str:
    """Update the quantity of a card in the active deck with deck construction validation.

    This tool sets the quantity of a card in the active deck to a specific value.
    Enforces Standard format deck construction rules:
    - Maximum 4 copies of any non-basic land card
    - Basic lands are unlimited
    - Quantity 0 removes the card from the deck

    If the card is not in the deck, it will be added with the specified quantity.

    Args:
        ctx: PydanticAI run context with agent dependencies
        card_name: Card name (user-provided via natural language)
        quantity: New quantity to set (0 removes the card)
        sideboard: True for sideboard, False for mainboard (default)

    Returns:
        User-friendly confirmation or error message

    Examples:
        User: "change Lightning Bolt to 4 copies"
        Agent invokes: update_card_quantity(ctx, card_name="Lightning Bolt", quantity=4)
        Returns: "Updated 'Lightning Bolt' to 4 copies in your deck."

        User: "set Mountain to 20"
        Agent invokes: update_card_quantity(ctx, card_name="Mountain", quantity=20)
        Returns: "Updated 'Mountain' to 20 copies in your deck."

        User: "set Lightning Bolt to 0"
        Agent invokes: update_card_quantity(ctx, card_name="Lightning Bolt", quantity=0)
        Returns: "Removed 'Lightning Bolt' from your deck."

    Error Cases:
        - No active deck: "No active deck. Create or load a deck first."
        - Card not found: "Card 'Xyz' not found in card database..."
        - Exceeds 4-copy limit: "Standard format allows maximum 4 copies of 'Lightning Bolt'..."
        - Invalid quantity: "Quantity must be 0 or greater."

    Notes:
        - Requires active deck in session context
        - Validates deck construction rules (4-copy limit except basic lands)
        - Quantity 0 triggers card removal
        - Adds card if not in deck
        - Returns clear error messages for all validation failures
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        deck = deps.active_deck

        # Defensive: Ensure clean session state before database operations
        if deps.deck_repository.session.in_transaction():
            await deps.deck_repository.session.rollback()

        # Check if active deck exists
        if deck is None:
            return "No active deck. Create or load a deck first."

        # Validate quantity
        if quantity < 0:
            return "Quantity must be 0 or greater."

        # Look up card by exact name
        card = await deps.card_repository.find_by_name_exact(
            card_name, format_filter=deps.format_filter
        )

        # If not found, try partial match for suggestions
        if card is None:
            suggestions = await deps.card_repository.find_by_name_partial(
                card_name, format_filter=deps.format_filter
            )
            if suggestions:
                suggestion_names = ", ".join([c.name for c in suggestions[:3]])
                return (
                    f"Card '{card_name}' not found in card database. "
                    f"Did you mean: {suggestion_names}?"
                )
            return (
                f"Card '{card_name}' not found in card database. Check spelling or use card search."
            )

        # Handle quantity 0 as removal
        if quantity == 0:
            # Remove card from deck
            success = await deps.deck_repository.remove_card_from_deck(
                deck_id=deck.id,
                card_id=card.id,
                sideboard=sideboard,
            )

            if success:
                location = "sideboard" if sideboard else "deck"
                return f"Removed '{card.name}' from your {location}."
            else:
                location = "sideboard" if sideboard else "deck"
                return f"'{card.name}' was not in your {location}."

        # Validate deck construction rules (max 4 copies except basic lands)
        is_basic_land = "basic" in card.type_line.lower() and "land" in card.type_line.lower()

        if not is_basic_land and quantity > 4:
            return (
                f"Standard format allows maximum 4 copies of '{card.name}'. "
                f"(Basic lands are unlimited.)"
            )

        # Find card in deck
        existing_card = next(
            (dc for dc in deck.deck_cards if dc.card_id == card.id and dc.sideboard == sideboard),
            None,
        )

        if existing_card:
            # Update existing quantity
            result = await deps.deck_repository.update_card_quantity(
                deck_id=deck.id,
                card_id=card.id,
                quantity=quantity,
                sideboard=sideboard,
            )

            if result:
                location = "sideboard" if sideboard else "deck"
                copies_text = "copy" if quantity == 1 else "copies"
                return f"Updated '{card.name}' to {quantity} {copies_text} in your {location}."
            else:
                return f"Failed to update '{card.name}' quantity. Please try again."
        else:
            # Add new card with specified quantity
            try:
                await deps.deck_repository.add_card_to_deck(
                    deck_id=deck.id,
                    card_id=card.id,
                    quantity=quantity,
                    sideboard=sideboard,
                )

                location = "sideboard" if sideboard else "deck"
                copies_text = "copy" if quantity == 1 else "copies"
                return f"Added {quantity} {copies_text} of '{card.name}' to your {location}."

            except Exception as e:
                return f"Failed to add '{card.name}' to deck. Error: {str(e)}\n\nPlease try again."

    except Exception as e:
        # Handle unexpected errors gracefully
        return (
            f"Failed to update card quantity for '{card_name}'. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def list_decks(
    ctx: RunContext[AgentDependencies], format_filter: str | None = None
) -> str | dict[str, Any]:
    """List all saved decks with names, formats, and basic statistics.

    This tool retrieves all saved decks from the database and displays them
    in a formatted list. Optionally filters by format (e.g., "standard").

    Decks are ordered by created_at descending (newest first).

    Args:
        ctx: PydanticAI run context with agent dependencies
        format_filter: Optional format to filter by (e.g., "standard")

    Returns:
        When decks exist: dict with keys:
            - has_decks: bool (True)
            - decks: list[Deck] (top 5 most recent decks)
            - formatted_text: str (formatted deck list as markdown)
        When no decks: str (error message)

    Examples:
        User: "show my decks"
        Agent invokes: list_decks(ctx)
        Returns: Formatted list of all decks with names, formats, card counts

        User: "show my standard decks"
        Agent invokes: list_decks(ctx, format_filter="standard")
        Returns: Filtered list of standard format decks only

    Error Cases:
        - No decks exist: "No decks found. Create a new deck to get started!"
        - Database error: "Failed to list decks. Error: ..."

    Notes:
        - Returns formatted markdown (UI-independent)
        - Shows deck ID for reference
        - Decks ordered newest first
        - Includes total mainboard card count
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps

        # Retrieve all decks (with optional format filter)
        decks = await deps.deck_repository.list_decks(format_filter=format_filter)

        # Import formatter here to avoid circular import at module level
        from src.ui.formatters import format_deck_list

        # Format deck list for display
        formatted_list = format_deck_list(decks)

        # If decks exist, return structured data with top 5 for quick-load
        if decks:
            return {
                "has_decks": True,
                "decks": decks[:5],  # Top 5 most recent decks for quick-load buttons
                "formatted_text": formatted_list,
            }

        # No decks - return string (backward compatible)
        return formatted_list

    except Exception as e:
        # Handle database or other errors gracefully
        return (
            f"Failed to list decks. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def load_deck(
    ctx: RunContext[AgentDependencies],
    name: str | None = None,
    deck_id: str | None = None,
) -> str:
    """Load a previously saved deck by name or ID and set it as the active deck.

    This tool retrieves a deck from the database and sets it as the active deck
    in the session context. Supports lookup by exact name match, partial name
    match (case-insensitive), or deck ID.

    Automatically synchronizes the format filter to match the deck's format:
    - For Standard, Modern, Commander, etc.: Sets format filter to match
    - For "all" format or None: Clears format filter
    - Ensures card searches return only format-legal cards by default

    Once loaded, all subsequent deck operations (add card, view, etc.) will
    operate on this deck, and card searches will respect the deck's format.

    Args:
        ctx: PydanticAI run context with agent dependencies
        name: Deck name for lookup (supports partial match)
        deck_id: Deck UUID for exact lookup

    Returns:
        Formatted deck summary confirming load, or error message

    Examples:
        User: "load my Mono Red Aggro deck"
        Agent invokes: load_deck(ctx, name="Mono Red Aggro")
        Returns: "**Loaded: Mono Red Aggro**\nFormat: Standard\nMainboard: 60 cards..."
        (Format filter auto-set to "standard")

        User: "load deck deck-abc-123"
        Agent invokes: load_deck(ctx, deck_id="deck-abc-123")
        Returns: Deck summary with confirmation

    Error Cases:
        - No name or ID provided: "Please specify a deck name or ID to load."
        - Deck not found by name: "Deck 'Xyz' not found. Try 'list my decks'..."
        - Deck not found by ID: "Deck with ID 'xyz' not found..."
        - Database error: "Failed to load deck. Error: ..."

    Notes:
        - Sets loaded deck as active via session manager
        - Auto-sets format filter to match deck format
        - Supports case-insensitive partial name matching
        - Replaces any previously active deck in session
        - Returns formatted summary with card counts
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        session_id = deps.session_id

        # Validate inputs
        if name is None and deck_id is None:
            return "Please specify a deck name or ID to load."

        # Find deck by ID or name
        deck = None

        if deck_id is not None:
            # Load by exact ID
            deck = await deps.deck_repository.get_deck_with_cards(deck_id)

            if deck is None:
                return (
                    f"Deck with ID '{deck_id}' not found. "
                    f"Try 'list my decks' to see available decks."
                )

        elif name is not None:
            # Try to find by partial name match
            deck = await deps.deck_repository.find_deck_by_name(name)

            if deck is None:
                return (
                    f"Deck '{name}' not found. Try 'list my decks' to see available decks, "
                    f"or check the spelling."
                )

            # Reload with cards for display
            deck = await deps.deck_repository.get_deck_with_cards(deck.id)

        if deck is None:
            return "Failed to load deck. Please try again."

        # Set deck as active in session manager
        _session_manager.set_active_deck_id(session_id, deck.id)

        # Update cached active deck in dependencies for current agent run
        # This ensures subsequent tools in the same turn see the loaded deck
        deps.active_deck = deck

        # Auto-set format filter to match deck format
        if deck.format and deck.format.lower() != "all":
            # Set format filter to match deck format (e.g., "standard", "modern")
            _session_manager.set_format_filter(session_id, deck.format.lower())
        else:
            # Clear format filter for "all" format or None
            _session_manager.clear_format_filter(session_id)

        # Calculate card counts
        card_count_mainboard = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)
        card_count_sideboard = sum(dc.quantity for dc in deck.deck_cards if dc.sideboard)

        # Import formatter here to avoid circular import at module level
        from src.ui.formatters import format_deck_summary

        # Format deck summary for display
        formatted_summary = format_deck_summary(deck, card_count_mainboard, card_count_sideboard)

        # Request sidebar update to show loaded deck
        deps.sidebar_needs_update = True

        return formatted_summary

    except Exception as e:
        # Handle database or other errors gracefully
        return (
            f"Failed to load deck. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def delete_deck(
    ctx: RunContext[AgentDependencies],
    name: str | None = None,
    deck_id: str | None = None,
    confirmed: bool = False,
) -> str | dict[str, str | bool]:
    """Delete a deck by name or ID with explicit confirmation requirement.

    This tool deletes a deck from the database, including all associated cards.
    Requires explicit confirmation (confirmed=True) to prevent accidental deletion.

    If the deleted deck is currently active in the session, the active deck
    will be cleared.

    Args:
        ctx: PydanticAI run context with agent dependencies
        name: Deck name for lookup (supports partial match)
        deck_id: Deck UUID for exact lookup
        confirmed: Explicit confirmation flag (default: False)

    Returns:
        When confirmed=False: Dict with needs_confirmation signal for UI to display action buttons
        When confirmed=True: Success message string
        On error: Error message string

    Examples:
        User: "delete Test Deck"
        Agent invokes: delete_deck(ctx, name="Test Deck", confirmed=False)
        Returns: "⚠ Are you sure you want to delete 'Test Deck'?..."

        User confirms: "yes, delete it"
        Agent invokes: delete_deck(ctx, name="Test Deck", confirmed=True)
        Returns: "Deleted deck 'Test Deck' successfully."

    Error Cases:
        - No name or ID provided: "Please specify a deck name or ID to delete."
        - Confirmation not provided: "⚠ Are you sure? Use confirmed=True..."
        - Deck not found by name: "Deck 'Xyz' not found..."
        - Deck not found by ID: "Deck with ID 'xyz' not found..."
        - Database error: "Failed to delete deck. Error: ..."

    Notes:
        - Requires confirmed=True to complete deletion (safety feature)
        - Clears active deck from session if deleted deck was active
        - Cascades to delete all associated deck_cards records
        - Supports case-insensitive partial name matching
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        session_id = deps.session_id
        active_deck = deps.active_deck

        # Defensive: Ensure clean session state before database operations
        if deps.deck_repository.session.in_transaction():
            await deps.deck_repository.session.rollback()

        # Validate inputs
        if name is None and deck_id is None:
            return "Please specify a deck name or ID to delete."

        # Find deck by ID or name
        deck = None

        if deck_id is not None:
            # Load by exact ID
            deck = await deps.deck_repository.get_deck(deck_id)

            if deck is None:
                return (
                    f"Deck with ID '{deck_id}' not found. "
                    f"Try 'list my decks' to see available decks."
                )

        elif name is not None:
            # Try to find by partial name match
            deck = await deps.deck_repository.find_deck_by_name(name)

            if deck is None:
                return (
                    f"Deck '{name}' not found. Try 'list my decks' to see available decks, "
                    f"or check the spelling."
                )

        if deck is None:
            return "Failed to find deck. Please try again."

        # Check if confirmation provided
        if not confirmed:
            # Return structured signal for UI to display action buttons
            return {
                "needs_confirmation": True,
                "deck_id": str(deck.id),
                "deck_name": deck.name,
            }

        # Delete deck from database
        success = await deps.deck_repository.delete_deck(deck.id)

        if not success:
            return f"Failed to delete deck '{deck.name}'. The deck may have already been deleted."

        # Clear active deck from session if this was the active deck
        if active_deck and active_deck.id == deck.id:
            _session_manager.clear_active_deck_id(session_id)

        # Request sidebar update to clear sidebar (if deleted deck was active)
        deps.sidebar_needs_update = True

        return f"Deleted deck '{deck.name}' successfully."

    except Exception as e:
        # Handle database or other errors gracefully
        return (
            f"Failed to delete deck. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )


async def update_deck_strategy(ctx: RunContext[AgentDependencies], strategy: str | None) -> str:
    """Update the strategy of the active deck.

    This tool allows users to set or modify the strategic description of their
    active deck. The strategy field can describe the deck's game plan, win conditions,
    or tactical approach. Passing None clears the strategy.

    The agent can use the strategy field to provide more relevant card recommendations
    that align with the deck's intended playstyle.

    Args:
        ctx: PydanticAI run context with agent dependencies
        strategy: New strategy description, or None to clear strategy

    Returns:
        User-friendly confirmation message

    Examples:
        User: "update my deck strategy to fast aggro with burn spells"
        Agent invokes: update_deck_strategy(ctx, strategy="Fast aggro with burn spells")
        Returns: "Updated deck strategy to: Fast aggro with burn spells"

        User: "change strategy to control deck with counters and card draw"
        Agent invokes: update_deck_strategy(
            ctx, strategy="Control deck with counters and card draw"
        )
        Returns: "Updated deck strategy to: Control deck with counters and card draw"

        User: "remove the deck strategy" or "clear strategy"
        Agent invokes: update_deck_strategy(ctx, strategy=None)
        Returns: "Cleared deck strategy."

    Error Cases:
        - No active deck: "No active deck. Create or load a deck first."
        - Database error: "Failed to update deck strategy. Error: ..."

    Notes:
        - Requires active deck in session context
        - Strategy is optional metadata for better AI recommendations
        - Passing None clears the strategy field
        - Updates sidebar to show new strategy
    """
    try:
        # Extract dependencies from context
        deps = ctx.deps
        deck = deps.active_deck

        # Defensive: Ensure clean session state before database operations
        if deps.deck_repository.session.in_transaction():
            await deps.deck_repository.session.rollback()

        # Check if active deck exists
        if deck is None:
            return "No active deck. Create or load a deck first."

        # Update deck strategy via repository
        updated_deck = await deps.deck_repository.update_deck(deck_id=deck.id, strategy=strategy)

        if updated_deck is None:
            return f"Active deck not found (ID: {deck.id}). Please create a new deck."

        # Request sidebar update to show new strategy
        deps.sidebar_needs_update = True

        # Return confirmation message
        if strategy is None:
            return "Cleared deck strategy."
        else:
            return f"Updated deck strategy to: {strategy}"

    except Exception as e:
        # Handle database or other errors gracefully
        return (
            f"Failed to update deck strategy. Error: {str(e)}\n\n"
            f"Please try again or contact support if this issue persists."
        )

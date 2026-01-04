"""Card operation action callbacks.

This module contains Chainlit action callbacks for:
- Adding synergy-suggested cards to deck (quick-add)
- Card selection from disambiguation options (view or add)
"""

import logging

import chainlit as cl

from src.ui.action_callbacks import action_error_handler, remove_all_actions, validate_session_id

logger = logging.getLogger(__name__)


@cl.action_callback("add_suggested_card")
@action_error_handler
async def on_add_suggested_card(action: cl.Action) -> None:
    """Handle adding a synergy-suggested card to the active deck.

    Adds 1 copy of the specified card to the active deck, updates the sidebar,
    and removes the action button to prevent duplicate additions.

    Args:
        action: The action with payload containing card_name and card_id
    """
    # Import here to avoid circular dependency at module load time
    from src.ui.app import get_agent_dependencies, update_deck_sidebar_wrapper

    # Validate session ID
    session_id = validate_session_id()

    # Extract card info from payload
    card_name = action.payload.get("card_name")
    card_id = action.payload.get("card_id")

    if not card_name or not card_id:
        await cl.Message(content="❌ Error: Missing card information. Please try again.").send()
        await action.remove()
        return

    # Get agent dependencies to access repositories
    async with get_agent_dependencies(session_id) as deps:
        # Check if there's an active deck
        if deps.active_deck is None:
            await cl.Message(
                content=f"❌ Cannot add **{card_name}** - no active deck. "
                f"Create or load a deck first."
            ).send()
            # Keep button - user can load a deck and try again
            return

        try:
            # Add card to deck (quantity = 1)
            await deps.deck_repository.add_card_to_deck(
                deck_id=deps.active_deck.id,
                card_id=card_id,
                quantity=1,
                sideboard=False,
            )

            # Mark sidebar for update
            deps.sidebar_needs_update = True

            # Remove this action button
            await action.remove()

            # Send confirmation message
            success_message = f"✅ Added **{card_name}** to deck"
            await cl.Message(content=success_message).send()

            # Update sidebar to show new card
            await update_deck_sidebar_wrapper(session_id)

            logger.info(
                f"Added synergy card '{card_name}' (ID: {card_id}) to deck via quick-add | "
                f"Session: {session_id}"
            )

        except ValueError as e:
            # Max copies exceeded or other validation error
            error_message = f"❌ Cannot add **{card_name}**: {str(e)}"
            await cl.Message(content=error_message).send()
            await action.remove()
            logger.warning(
                f"Failed to add synergy card '{card_name}': {str(e)} | Session: {session_id}"
            )

        except Exception as e:
            # Unexpected error - log and notify user
            logger.error(
                f"Unexpected error adding synergy card '{card_name}' (ID: {card_id}): {str(e)} | "
                f"Session: {session_id}",
                exc_info=True,
            )
            error_message = f"❌ Failed to add **{card_name}**. Please try again."
            await cl.Message(content=error_message).send()
            await action.remove()


@cl.action_callback("select_card")
@action_error_handler
async def on_select_card(action: cl.Action) -> None:
    """Handle card selection from disambiguation options.

    Supports two contexts:
    - "view": Display card details
    - "add": Add card to active deck

    Args:
        action: The action with payload containing card_id, card_name, and context
    """
    # Import here to avoid circular dependency at module load time
    from src.ui.app import get_agent_dependencies, update_deck_sidebar_wrapper

    # Validate session ID
    session_id = validate_session_id()

    # Extract card info from payload
    card_id = action.payload.get("card_id")
    card_name = action.payload.get("card_name")
    context = action.payload.get("context", "view")  # Default to view

    if not card_id or not card_name:
        await cl.Message(content="❌ Error: Missing card information. Please try again.").send()
        await remove_all_actions("disambiguation_message")
        return

    # Get agent dependencies to access repositories
    async with get_agent_dependencies(session_id) as deps:
        try:
            # Load card from repository by name (most reliable for disambiguation)
            card = await deps.card_repository.find_by_name_exact(card_name)

            if card is None:
                error_message = f"❌ Card **'{card_name}'** not found. It may have been removed."
                await cl.Message(content=error_message).send()
                await remove_all_actions("disambiguation_message")
                logger.warning(
                    f"Card selection failed: card '{card_name}' (ID: {card_id}) not found | "
                    f"Session: {session_id}"
                )
                return

            # Handle based on context
            if context == "add":
                # Add context path: Add card to active deck
                if deps.active_deck is None:
                    await cl.Message(
                        content=f"❌ Cannot add **{card_name}** - no active deck. "
                        f"Create or load a deck first."
                    ).send()
                    # Keep buttons - user can load a deck and try again
                    return

                # Add card to deck (quantity = 1)
                await deps.deck_repository.add_card_to_deck(
                    deck_id=deps.active_deck.id,
                    card_id=card_id,
                    quantity=1,
                    sideboard=False,
                )

                # Mark sidebar for update
                deps.sidebar_needs_update = True

                # Remove all disambiguation buttons
                await remove_all_actions("disambiguation_message")

                # Send confirmation message
                success_message = f"✅ Added **{card_name}** to deck"
                await cl.Message(content=success_message).send()

                # Update sidebar to show new card
                await update_deck_sidebar_wrapper(session_id)

                logger.info(
                    f"Card '{card_name}' added to deck via disambiguation (add context) | "
                    f"Session: {session_id}"
                )

            else:
                # View context path: Display card details
                from src.ui.formatters import format_card_details, format_card_with_image

                # Format card details with image if available
                if card.image_uris:
                    text, image = format_card_with_image(card)
                    if image:
                        await cl.Message(content=text, elements=[image]).send()
                    else:
                        await cl.Message(content=format_card_details(card)).send()
                else:
                    await cl.Message(content=format_card_details(card)).send()

                # Remove all disambiguation buttons
                await remove_all_actions("disambiguation_message")

                logger.info(
                    f"Card '{card_name}' selected for viewing via disambiguation | "
                    f"Session: {session_id}"
                )

        except ValueError as e:
            # Max copies exceeded or other validation error (add context only)
            error_message = f"❌ Cannot add **{card_name}**: {str(e)}"
            await cl.Message(content=error_message).send()
            await remove_all_actions("disambiguation_message")
            logger.warning(
                f"Failed to add card '{card_name}' via disambiguation: {str(e)} | "
                f"Session: {session_id}"
            )

        except Exception as e:
            # Unexpected error - log and notify user
            logger.error(
                f"Unexpected error selecting card '{card_name}' (ID: {card_id}): {str(e)} | "
                f"Session: {session_id}",
                exc_info=True,
            )
            error_message = f"❌ Failed to select **{card_name}**. Please try again."
            await cl.Message(content=error_message).send()
            await remove_all_actions("disambiguation_message")

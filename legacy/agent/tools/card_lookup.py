"""Card lookup tool for PydanticAI agent.

This tool enables the agent to search for Magic: The Gathering cards by name
in the local Scryfall database. It implements intelligent fallback logic from
exact to partial matching and handles ambiguous queries gracefully.
"""

from typing import Any

from pydantic_ai import RunContext

from legacy.agent.dependencies import AgentDependencies
from legacy.ui.formatters import format_card_details, format_card_list, format_card_with_image


async def lookup_card_by_name(
    ctx: RunContext[AgentDependencies], card_name: str, auto_filter: bool = True
) -> str | dict[str, Any]:
    """Look up a Magic: The Gathering card by name.

    IMPORTANT - Context-Aware Usage:
    Before calling this tool for potentially ambiguous card names, check if there's an
    active deck loaded via ctx.deps.active_deck. If the deck contains a matching card,
    you should identify the exact card name from the deck, then call this tool with that
    exact name to get formatted details and images.

    Example - Context-Aware Lookup:
    - User has loaded deck "Tinybones Archon" with "Tinybones, the Pickpocket"
    - User asks: "tell me about tinybones"
    - CORRECT: Check active_deck.cards, find "Tinybones, the Pickpocket", call tool
      with that exact name
    - INCORRECT: Call this tool with "tinybones" and return 3 matching cards asking
      for clarification
    - ALSO INCORRECT: Respond from memory without calling this tool (you'll miss
      images and formatted output)

    Always call this tool to get properly formatted card information with images, but use deck
    context to determine WHICH card to look up when names are ambiguous.

    This tool searches the local Scryfall database for cards matching the
    given name. It first attempts an exact match (case-insensitive), then
    falls back to partial matching if no exact match is found.

    Respects the current format filter setting by default - if enabled, only
    cards legal in the specified format will be returned. The auto_filter
    parameter can be used to bypass format filtering temporarily.

    The tool handles ambiguous queries intelligently:
    - Single match: Returns full card details
    - Multiple matches (2-10): Lists all matches and asks for clarification
    - Many matches (>10): Lists first 10 and suggests refinement
    - No matches: Returns helpful "not found" message

    When ambiguous results exist and no deck context is available:
    - Present ALL matching options to the user
    - Ask them to clarify which card they meant
    - Provide enough info (set, type, year) to distinguish between options

    Args:
        ctx: RunContext providing access to agent dependencies
        card_name: Name of the card to search for. Can be partial (e.g., "bolt"
            will match "Lightning Bolt", "Shock Bolt", etc.)
        auto_filter: If True (default), respects session format filter. If False,
            bypasses format filter and searches all cards regardless of format.
            Use False when user explicitly asks to see cards "from any format"
            or "including non-Standard cards".

    Returns:
        When 1 match or 6+ matches or no matches: str (formatted card information or error message)
        When 2-5 matches: dict with keys:
            - needs_disambiguation: bool (True)
            - matches: list[Card] (2-5 Card objects for disambiguation)
            - formatted_text: str (formatted disambiguation message)

    Examples:
        >>> # Exact match
        >>> await lookup_card_by_name(ctx, "Lightning Bolt")
        Card: Lightning Bolt
        Mana Cost: {R}
        Type: Instant
        Text: Lightning Bolt deals 3 damage to any target.
        Colors: Red

        >>> # Ambiguous query
        >>> await lookup_card_by_name(ctx, "bolt")
        I found 15 cards matching 'bolt'. Here are the first 10:
        - Lightning Bolt
        - Bolt Bend
        - Thunderbolt
        ...
        Could you be more specific?

        >>> # Not found
        >>> await lookup_card_by_name(ctx, "Nonexistent Card")
        I couldn't find a card matching 'Nonexistent Card'. Could you check the spelling?

    Notes:
        - Exact matches are case-insensitive ("lightning bolt" = "Lightning Bolt")
        - Partial matches find any card with the query as a substring
        - Double-faced cards show both face names (e.g., "Delver // Aberration")
        - Oracle text is truncated to 200 characters for long cards
        - Respects format filter setting from context
    """
    repo = ctx.deps.card_repository
    # Use format filter and games filter only if auto_filter is True
    format_filter = ctx.deps.format_filter if auto_filter else None
    games_filter = ctx.deps.games_filter if auto_filter else None

    # Strategy: Try exact match first, fall back to partial match
    # This reduces ambiguity for queries like "Bolt" (exact: none, partial: many)

    # Attempt exact match (case-insensitive)
    card = await repo.find_by_name_exact(card_name, format_filter=format_filter, games=games_filter)
    if card:
        # Use image formatter if card has image URIs
        if card.image_uris:
            text, image = format_card_with_image(card)
            if image:
                ctx.deps.ui_elements.append(image)
            return text
        return format_card_details(card)

    # No exact match - try partial match
    cards = await repo.find_by_name_partial(
        card_name, format_filter=format_filter, games=games_filter
    )

    # Handle different result scenarios
    if not cards:
        # Provide context about format filtering if active and auto_filter=True
        filter_note = ""
        if format_filter and auto_filter:
            filter_note = (
                f" in {format_filter.title()}-legal cards. "
                f"(Format filter is active. To see all cards, try searching 'from any format'.)"
            )
        return (
            f"I couldn't find a card matching '{card_name}'{filter_note}. "
            "Could you check the spelling or try a different search term?"
        )

    if len(cards) == 1:
        # Single partial match - return it with image if available
        card = cards[0]
        if card.image_uris:
            text, image = format_card_with_image(card)
            if image:
                ctx.deps.ui_elements.append(image)
            return text
        return format_card_details(card)

    # Multiple matches - use list formatter
    # Format filter indicator for multiple results (only if auto_filter=True)
    filter_note = (
        f"\n\n(Showing {format_filter.title()}-legal cards only)"
        if format_filter and auto_filter
        else ""
    )

    intro = f"I found {len(cards)} cards matching '{card_name}':{filter_note}\n\n"
    card_list = format_card_list(cards, limit=10)
    formatted_text = f"{intro}{card_list}\n\nWhich one did you mean?"

    # If 2-5 matches, return structured data for disambiguation actions
    if 2 <= len(cards) <= 5:
        return {
            "needs_disambiguation": True,
            "matches": cards,  # Full Card objects for action rendering
            "formatted_text": formatted_text,
        }

    # For 6+ matches, return text only (conversational disambiguation)
    return formatted_text

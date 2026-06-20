"""Advanced card search tool for PydanticAI agent.

This tool enables the agent to perform sophisticated card searches using multiple
filter criteria including colors, types, keywords, and mana value ranges.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from legacy.agent.dependencies import AgentDependencies
from src.data.schemas.card import Card
from src.data.schemas.pagination import PaginatedResult
from legacy.ui.formatters import format_card_list, format_card_with_image


class CardSearchFilters(BaseModel):
    """Filter criteria for advanced card search.

    This model defines the available search parameters for filtering cards.
    All filters are optional and are combined with AND logic (cards must
    match all specified criteria).

    Attributes:
        colors: List of color codes (W/U/B/R/G). Cards must contain at least
            one of the specified colors. For example, ["R"] finds red cards,
            ["R", "G"] finds cards that are red OR green (or both).
        types: List of type strings to search for in the type line. Cards must
            match ALL specified types. For example, ["Creature", "Dragon"] finds
            creature cards that are also dragons.
        keywords: List of keyword abilities to search for. Cards must have ALL
            specified keywords. Searches both the keywords array and oracle text.
            For example, ["haste", "flying"] finds cards with both abilities.
        oracle_text: List of text phrases to search for in the oracle text.
            ALL phrases must appear in the card's oracle text (AND logic).
            Case-insensitive substring matching. For example,
            ["target creature you control", "gains flying"] finds only cards
            whose oracle text contains both phrases.
        mana_value_min: Minimum mana value (CMC) inclusive. For example, 2 finds
            cards with CMC >= 2.
        mana_value_max: Maximum mana value (CMC) inclusive. For example, 3 finds
            cards with CMC <= 3.
        page: Page number for pagination (1-indexed). Use for "next page" requests.
            Defaults to 1.
        page_size: Number of results per page (max 50). Defaults to 20.
        max_results: DEPRECATED. Use page_size instead. Maintained for backward
            compatibility.

    Examples:
        >>> # Find red creatures with haste under 4 mana
        >>> filters = CardSearchFilters(
        ...     colors=["R"],
        ...     types=["Creature"],
        ...     keywords=["haste"],
        ...     mana_value_max=3,
        ...     page_size=20
        ... )

        >>> # Find rare or mythic black cards
        >>> filters = CardSearchFilters(
        ...     colors=["B"],
        ...     rarity=["rare", "mythic"]
        ... )

        >>> # Find cards with specific oracle text
        >>> filters = CardSearchFilters(
        ...     oracle_text=["target creature you control", "gains flying"]
        ... )

        >>> # Pagination example
        >>> filters = CardSearchFilters(
        ...     colors=["U"],
        ...     types=["Instant"],
        ...     page=2,
        ...     page_size=15
        ... )
    """

    colors: list[str] | None = Field(
        default=None,
        description="Color codes (W/U/B/R/G). How this is interpreted depends on color_mode.",
    )
    color_mode: Literal["any", "all", "exact", "at_most"] | None = Field(
        default="any",
        description=(
            "How to interpret the colors filter:\n"
            "- 'any': Contains ANY specified color (OR logic) - default\n"
            "- 'all': Contains ALL specified colors (AND logic)\n"
            "- 'exact': Exactly these colors, no more, no less\n"
            "- 'at_most': Only these colors or fewer (color identity)\n\n"
            "Examples:\n"
            "- colors=['W', 'U'], mode='any': white OR blue (mono-W, mono-U, W/U, multicolor)\n"
            "- colors=['W', 'U'], mode='all': multicolor with both W AND U (W/U, W/U/R, etc.)\n"
            "- colors=['W', 'U'], mode='exact': Azorius (W/U) only (not mono, not tricolor)\n"
            "- colors=['W', 'U'], mode='at_most': colorless, mono-W, mono-U, or W/U only\n\n"
            "MTG terminology examples:\n"
            "- 'Azorius cards' → colors=['W', 'U'], color_mode='exact'\n"
            "- 'White and blue cards' → colors=['W', 'U'], color_mode='all' or 'exact'\n"
            "- 'White or blue cards' → colors=['W', 'U'], color_mode='any'\n"
            "- 'Cards in white-blue identity' → colors=['W', 'U'], color_mode='at_most'"
        ),
    )
    types: list[str] | None = Field(
        default=None,
        description="Card types to search for in type line (e.g., Creature, Instant, Dragon). "
        "Cards must match ALL specified types.",
    )
    keywords: list[str] | None = Field(
        default=None,
        description="Keyword abilities (e.g., haste, flying, trample). "
        "Cards must have ALL specified keywords.",
    )
    oracle_text: list[str] | None = Field(
        default=None,
        description="Oracle text phrases to search for (case-insensitive). "
        "ALL phrases must appear in the card's oracle text. "
        "For example: ['target creature you control', 'gains flying'] finds only cards "
        "whose oracle text contains both phrases.",
    )
    mana_value_min: float | None = Field(
        default=None,
        description="Minimum mana value (CMC) inclusive. For example, 2 finds cards with CMC >= 2.",
    )
    mana_value_max: float | None = Field(
        default=None,
        description="Maximum mana value (CMC) inclusive. For example, 3 finds cards with CMC <= 3.",
    )
    rarity: str | list[str] | None = Field(
        default=None,
        description="Card rarity filter (case-insensitive). "
        "Valid values: common, uncommon, rare, mythic, special, bonus. "
        "For single rarity: 'rare'. For multiple: ['rare', 'mythic'] (OR logic).",
    )
    page: int = Field(
        default=1,
        description="Page number for pagination (1-indexed). Use for 'next page' requests.",
    )
    page_size: int = Field(
        default=20,
        description="Number of results per page (max 50).",
    )
    max_results: int | None = Field(
        default=None,
        description="DEPRECATED: Use page_size instead. Maintained for backward compatibility.",
    )


def _format_search_results_paginated(
    result: PaginatedResult[Card],
    filters: CardSearchFilters,
    format_filter: str | None = None,
    auto_filter: bool = True,
) -> str:
    """Format paginated search results for display.

    Args:
        result: PaginatedResult containing cards and pagination metadata
        filters: Original search filters used
        format_filter: Active format filter (e.g., "standard" or None)
        auto_filter: Whether auto-filtering was enabled for this search

    Returns:
        Formatted search results message with pagination metadata
    """
    if not result.items:
        # No results - provide helpful suggestions
        suggestions = []
        if filters.colors:
            suggestions.append("try different colors")
        if filters.mana_value_max is not None and filters.mana_value_max < 3:
            suggestions.append("increase the mana value range")
        if filters.keywords and len(filters.keywords) > 1:
            suggestions.append("search for fewer keywords")
        if filters.oracle_text and len(filters.oracle_text) > 1:
            suggestions.append("try fewer oracle text phrases")
        if filters.types and len(filters.types) > 1:
            suggestions.append("search for fewer card types")
        if format_filter and auto_filter:
            suggestions.append("try searching 'from any format' to see all cards")

        suggestion_text = " or ".join(suggestions) if suggestions else "relax some filter criteria"

        return (
            "I couldn't find any cards matching those criteria. "
            f"Try to {suggestion_text} to see more results."
        )

    # Calculate display range
    start_index = (result.page - 1) * result.page_size + 1
    end_index = start_index + len(result.items) - 1

    # Build result header with pagination
    result_text = f"Found {result.total_count} card{'s' if result.total_count != 1 else ''}"

    if result.total_pages > 1:
        result_text += (
            f" (Page {result.page} of {result.total_pages}, showing {start_index}-{end_index})"
        )
    elif result.total_count > result.page_size:
        result_text += f" (showing {start_index}-{end_index})"

    # Add format filter indicator (only if auto_filter=True)
    if format_filter and auto_filter:
        result_text += f" - {format_filter.title()}-legal cards only"

    result_text += ":\n\n"

    # Abbreviated search results to reduce context consumption
    # Show first 10 cards with full details, rest as compact list
    full_detail_count = 10

    if len(result.items) <= full_detail_count:
        # All cards fit in full detail - use standard formatter
        card_list = format_card_list(result.items, limit=len(result.items))
        result_text += card_list
    else:
        # Show first 10 with full details
        full_detail_cards = result.items[:full_detail_count]
        card_list = format_card_list(full_detail_cards, limit=full_detail_count)
        result_text += card_list

        # Add compact list for remaining cards
        result_text += "\n\n**Additional Results** (compact view):\n\n"
        from legacy.ui.formatters import (
            format_mana_symbols,
            get_display_name,
            wrap_card_name_with_hover,
        )

        for i, card in enumerate(result.items[full_detail_count:], start=full_detail_count + 1):
            # Preserve card image hover for all results
            display_name = get_display_name(card)
            card_name_with_hover = wrap_card_name_with_hover(display_name, card)

            # Format mana cost
            mana_symbols = format_mana_symbols(card.mana_cost) if card.mana_cost else ""
            mana_part = f" {mana_symbols}" if mana_symbols else ""

            # Compact format: "N. Card Name {cost} - Type"
            result_text += f"{i}. {card_name_with_hover}{mana_part} - {card.type_line}\n"

        result_text += "\n_Use filters or pagination to see more details._\n"

    # Add filter summary if multiple filters were applied
    filter_parts = []
    if filters.colors:
        color_names = {
            "W": "white",
            "U": "blue",
            "B": "black",
            "R": "red",
            "G": "green",
        }
        colors_str = " or ".join(color_names.get(c, c) for c in filters.colors)
        filter_parts.append(colors_str)
    if filters.types:
        filter_parts.append(" ".join(filters.types).lower())
    if filters.keywords:
        filter_parts.append(f"with {', '.join(filters.keywords)}")
    if filters.oracle_text:
        # Format oracle text phrases for display
        phrases_str = "', '".join(filters.oracle_text)
        filter_parts.append(f"oracle text: '{phrases_str}'")
    if filters.rarity:
        # Format rarity for display
        rarity_list = [filters.rarity] if isinstance(filters.rarity, str) else filters.rarity
        if len(rarity_list) == 1:
            filter_parts.append(f"{rarity_list[0]} rarity")
        else:
            filter_parts.append(f"{' or '.join(rarity_list)} rarity")
    if filters.mana_value_max is not None:
        if filters.mana_value_min is not None:
            filter_parts.append(f"CMC {filters.mana_value_min}-{filters.mana_value_max}")
        else:
            filter_parts.append(f"CMC ≤ {filters.mana_value_max}")
    elif filters.mana_value_min is not None:
        filter_parts.append(f"CMC ≥ {filters.mana_value_min}")

    if filter_parts and len(result.items) > 5:
        result_text += f"\n\nFilters: {' '.join(filter_parts)}"

    # Add pagination navigation hints
    if result.total_pages > 1:
        remaining = result.total_count - end_index
        if result.page < result.total_pages:
            result_text += (
                f"\n\nThere are {remaining} more results. "
                f"Say 'next page' or 'show me more' to see page {result.page + 1}."
            )
        elif result.page > 1:
            result_text += "\n\nYou're on the last page."

    return result_text


async def search_cards_advanced(
    ctx: RunContext[AgentDependencies],
    filters: CardSearchFilters,
    auto_filter: bool = True,
) -> str | dict[str, Any]:
    """Search for cards using multiple filter criteria with pagination.

    This tool performs advanced card searches using any combination of color,
    type, keyword, oracle text, and mana value filters. All filters use AND logic -
    cards must match ALL specified criteria to be included in results.

    Respects the current format filter setting by default - if enabled, only
    cards legal in the specified format will be returned. The auto_filter
    parameter can be used to bypass format filtering temporarily.

    The tool returns a paginated, formatted list of matching cards, sorted by mana
    value and name.

    Args:
        ctx: RunContext providing access to agent dependencies
        filters: CardSearchFilters model containing search criteria
        auto_filter: If True (default), respects session format filter. If False,
            bypasses format filter and searches all cards regardless of format.
            Use False when user explicitly asks to see cards "from any format"
            or "including non-Standard cards".

    Returns:
        Formatted search results as a string, including:
        - Number of total matches with pagination info
        - Numbered list of cards for current page
        - Brief card details (name, mana cost, type, P/T if creature)
        - Filter summary for complex searches
        - Pagination navigation hints
        - Helpful suggestions if no results found

    Examples:
        >>> # Find red creatures with haste under 4 mana
        >>> filters = CardSearchFilters(
        ...     colors=["R"],
        ...     types=["Creature"],
        ...     keywords=["haste"],
        ...     mana_value_max=3,
        ...     page=1,
        ...     page_size=20
        ... )
        >>> result = await search_cards_advanced(ctx, filters)
        Found 45 cards (Page 1 of 3, showing 1-20):
        ...
        There are 25 more results. Say 'next page' or 'show me more' to see page 2.

        >>> # Find cards with specific oracle text
        >>> filters = CardSearchFilters(
        ...     oracle_text=["target creature you control", "gains flying"]
        ... )
        >>> result = await search_cards_advanced(ctx, filters)
        Found 3 cards:
        1. Acrobatic Leap
        2. Fleeting Flight
        3. Secret Identity

    Notes:
        - Color filter logic controlled by color_mode parameter:
          * 'any' (default): ["R", "G"] finds red OR green cards
          * 'all': ["W", "U"] finds cards with both white AND blue
          * 'exact': ["W", "U"] finds only Azorius (W/U) cards
          * 'at_most': ["W", "U"] finds colorless, mono-W, mono-U, or W/U
        - Type filter uses AND logic: ["Creature", "Dragon"] finds creature dragons
        - Keyword filter uses AND logic: ["flying", "haste"] finds cards with BOTH
        - Oracle text filter uses AND logic: ALL phrases must appear in oracle text
        - Results are sorted by mana value (low to high), then alphabetically
        - Pagination: use page and page_size parameters to navigate results
        - max_results is deprecated; use page_size instead
        - If no results, provides context-aware suggestions to relax filters
        - Respects format filter setting from context
    """
    repo = ctx.deps.card_repository
    # Use format filter and games filter only if auto_filter is True
    format_filter = ctx.deps.format_filter if auto_filter else None
    games_filter = ctx.deps.games_filter if auto_filter else None

    # Handle backward compatibility with max_results
    page = filters.page
    page_size = filters.page_size
    if filters.max_results is not None:
        page_size = filters.max_results
        page = 1

    # Perform advanced search with filters and pagination
    result = await repo.search_advanced(
        colors=filters.colors,
        types=filters.types,
        keywords=filters.keywords,
        oracle_text_phrases=filters.oracle_text,
        mana_value_min=filters.mana_value_min,
        mana_value_max=filters.mana_value_max,
        rarity=filters.rarity,
        page=page,
        page_size=page_size,
        format_filter=format_filter,
        games=games_filter,
        color_mode=filters.color_mode or "any",
    )

    # Store search context for pagination if results span multiple pages
    if result.total_pages > 1:
        search_context = {
            "colors": filters.colors,
            "types": filters.types,
            "keywords": filters.keywords,
            "oracle_text": filters.oracle_text,
            "mana_value_min": filters.mana_value_min,
            "mana_value_max": filters.mana_value_max,
            "rarity": filters.rarity,
            "page_size": page_size,
            "color_mode": filters.color_mode or "any",
            "format_filter": format_filter,
            "games": games_filter,
            "auto_filter": auto_filter,
        }
        # Store in session manager for later retrieval during pagination
        ctx.deps._session_manager.set_search_context(ctx.deps.session_id, search_context)

    # If exactly one card result and it has an image, add image element
    if result.total_count == 1 and result.items[0].image_uris:
        card = result.items[0]
        text, image = format_card_with_image(card)
        if image:
            ctx.deps.ui_elements.append(image)
        return text

    # For paginated results, return structured data for UI to add pagination buttons
    if result.total_pages > 1:
        formatted_text = _format_search_results_paginated(
            result, filters, format_filter, auto_filter
        )
        return {
            "has_pagination": True,
            "page": result.page,
            "total_pages": result.total_pages,
            "total_count": result.total_count,
            "cards": result.items,
            "formatted_text": formatted_text,
        }

    # Format and return results with pagination (single page)
    return _format_search_results_paginated(result, filters, format_filter, auto_filter)

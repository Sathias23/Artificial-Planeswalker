"""Synergy-based card suggestion tool for agent.

This module provides LLM-hybrid card suggestions that analyze deck composition
and recommend cards that synergize with the current deck strategy.

The workflow consists of three stages:
1. Analysis Stage: LLM analyzes deck and generates search criteria
2. Search Stage: Parallel database searches retrieve candidates
3. Curation Stage: LLM evaluates candidates and selects top picks
"""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from legacy.agent.config import AgentConfig
from legacy.agent.dependencies import AgentDependencies
from src.data.repositories.card import CardRepository
from src.data.schemas import Card
from src.data.schemas.deck import Deck
from src.logic.mana_curve import analyze_mana_curve
from src.logic.synergy import detect_synergies
from legacy.ui.formatters import get_display_name, wrap_card_name_with_hover

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Structured Output (AC2)
# =============================================================================


class DeckNeedAnalysis(BaseModel):
    """Individual search criteria for deck improvement needs.

    Represents a single deck need that can be addressed through card search,
    including the specific parameters for the database query.
    """

    need_type: str = Field(
        ...,
        description=(
            "Category of deck need: 'creature', 'removal', 'card_draw', "
            "'mana_ramp', 'finisher', 'synergy_enabler', 'protection', "
            "'utility', 'tribal', 'keyword'"
        ),
    )
    description: str = Field(
        ...,
        description="Brief explanation of why the deck needs this (e.g., 'lacks early creatures')",
    )
    search_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to search for in oracle text (e.g., ['draw', 'card'])",
    )
    search_types: list[str] = Field(
        default_factory=list,
        description="Card types to search for (e.g., ['Creature', 'Instant'])",
    )
    max_cmc: int | None = Field(
        default=None,
        description="Maximum converted mana cost for this search (e.g., 3 for early plays)",
    )


class DeckAnalysis(BaseModel):
    """Analysis of deck composition and synergy needs.

    Structured output from the analysis LLM agent containing the primary
    synergy strategy identified and search criteria for finding improvements.
    """

    primary_synergy: str = Field(
        ...,
        description=(
            "Main synergy theme identified (e.g., 'Goblin tribal', "
            "'graveyard recursion', 'artifact synergy')"
        ),
    )
    search_criteria: list[DeckNeedAnalysis] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3-5 specific search criteria to find complementary cards",
    )
    reasoning: str = Field(
        ...,
        description=(
            "Explanation of analysis including mana curve observations, "
            "synergy patterns, and improvement priorities"
        ),
    )


class CuratedCard(BaseModel):
    """A single curated card recommendation with explanation.

    Represents one card selected from candidates with synergy fit
    explanation and priority ranking.
    """

    card_name: str = Field(
        ...,
        description="Exact card name as it appears in the candidate list",
    )
    synergy_fit: str = Field(
        ...,
        description=(
            "Explanation of how this card synergizes with the deck "
            "(e.g., 'Triggers death effects while providing card advantage')"
        ),
    )
    priority: int = Field(
        ...,
        ge=1,
        le=5,
        description="Priority ranking from 1 (highest) to 5 (lowest priority)",
    )


class CardSuggestions(BaseModel):
    """Curated card suggestions from the analysis.

    Final output containing the top card recommendations with
    explanations and an overall strategy summary.
    """

    top_picks: list[CuratedCard] = Field(
        ...,
        min_length=5,
        max_length=7,
        description="5-7 top card recommendations with explanations",
    )
    overall_strategy: str = Field(
        ...,
        description=(
            "Summary of how these cards improve the deck as a cohesive unit "
            "(e.g., 'These additions strengthen the sacrifice subtheme while "
            "improving early-game presence')"
        ),
    )


# =============================================================================
# Agent Creation (Provider Pattern from core.py)
# =============================================================================


def _create_suggestion_agents() -> tuple[Agent[None, DeckAnalysis], Agent[None, CardSuggestions]]:
    """Create analysis and curation agents using project's provider pattern.

    Uses the same provider selection logic as the main agent to ensure
    consistent model usage across the application.

    Returns:
        Tuple of (analysis_agent, curation_agent)
    """
    config = AgentConfig()

    # Reuse provider determination logic from core.py
    from legacy.agent.core import _determine_provider

    use_anthropic, model_name = _determine_provider(config)

    # Create model instance (same pattern as create_agent())
    model: AnthropicModel | OpenAIChatModel
    if use_anthropic:
        anthropic_provider = AnthropicProvider(api_key=config.anthropic_api_key)
        model = AnthropicModel(model_name=model_name, provider=anthropic_provider)
    else:
        openai_provider = OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key,
        )
        model = OpenAIChatModel(model_name=model_name, provider=openai_provider)

    # Analysis agent: Analyze deck and generate search criteria
    analysis_agent: Agent[None, DeckAnalysis] = Agent(
        model=model,
        output_type=DeckAnalysis,
        system_prompt="""You are an expert Magic: The Gathering deck analyst.

Your task is to analyze a deck's composition and identify what cards would improve it.

When analyzing:
1. Identify the primary synergy theme (tribal, keyword, mechanic, archetype)
2. Evaluate mana curve balance and gaps
3. Consider what the deck does well and where it struggles
4. Generate 3-5 specific search criteria to find helpful additions

For mana curve considerations:
- Aggro decks (avg CMC ≤ 2.5): Prioritize 1-2 mana plays
- Midrange decks (avg CMC 2.5-3.5): Balance across 2-4 mana
- Control decks (avg CMC > 3.5): Need both early interaction and late-game finishers
- If deck is top-heavy (>25% at 5+ CMC), bias searches toward lower CMC cards
- If lacking early plays (few 1-2 drops), include low-CMC search criteria

Generate search criteria that will find cards complementing the deck's strengths
while addressing its weaknesses. Each criterion should be specific enough to
return useful results but broad enough to find multiple options.""",
    )

    # Curation agent: Evaluate candidates and select best picks
    curation_agent: Agent[None, CardSuggestions] = Agent(
        model=model,
        output_type=CardSuggestions,
        system_prompt="""You are an expert Magic: The Gathering deck builder.

Your task is to evaluate candidate cards and select the 5-7 best additions for a deck.

When evaluating candidates:
1. Prioritize cards that synergize with multiple elements of the deck
2. Consider mana curve impact - prefer cards that fill gaps
3. Avoid redundant effects if the deck already has that covered
4. Value versatility - cards with multiple uses are often better
5. Consider the deck's overall strategy and how each card advances it

CRITICAL: You may ONLY select cards from the provided candidate list.
Do NOT suggest cards that are not in the candidate list - this will cause errors.
If you're unsure about a card name, verify it exists in the candidates before selecting.

For each selection:
- Use the EXACT card name as it appears in the candidate list
- Explain specifically how it synergizes with existing cards
- Assign priority 1 (highest) to 5 (lowest) based on impact

Your overall_strategy should explain how these additions work together
to strengthen the deck as a cohesive unit.""",
    )

    return analysis_agent, curation_agent


# =============================================================================
# Helper Functions
# =============================================================================


def _build_deck_context(deck: Deck) -> str:
    """Build deck context string for analysis agent.

    Compiles comprehensive deck information including card composition,
    mana curve analysis, synergy patterns, and color identity.

    Args:
        deck: Deck schema instance with cards loaded

    Returns:
        Formatted string context for LLM analysis
    """
    # CRITICAL: Convert DeckCard to Card list for mana_curve.analyze_mana_curve()
    # analyze_mana_curve expects list[Card], not list[DeckCard]
    mainboard_deck_cards = [dc for dc in deck.deck_cards if not dc.sideboard]
    cards_expanded: list[Card] = [
        dc.card
        for dc in mainboard_deck_cards
        for _ in range(dc.quantity)  # Expand by quantity
    ]

    # Get mana curve analysis
    if cards_expanded:
        curve_analysis = analyze_mana_curve(cards_expanded)
        avg_cmc = curve_analysis.average_cmc
        curve_issues = curve_analysis.issues
        curve_distribution = curve_analysis.distribution
    else:
        avg_cmc = 0.0
        curve_issues = ["Deck is empty"]
        curve_distribution = {}

    # Color identity with fallback computation
    if deck.color_identity:
        colors = deck.color_identity
    else:
        # Compute from cards if deck.color_identity is empty (new decks)
        colors = list({c for dc in mainboard_deck_cards for c in (dc.card.color_identity or [])})

    # Get synergy analysis
    synergy_analysis = detect_synergies(mainboard_deck_cards)
    synergy_summary = []
    for synergy in synergy_analysis.synergies:
        synergy_summary.append(
            f"- {synergy.pattern_type.capitalize()} ({synergy.subtype}): {synergy.explanation}"
        )

    # Build context sections
    context_parts = [
        f"Deck: {deck.name}",
        f"Format: {deck.format or 'all'}",
        f"Colors: {', '.join(colors) if colors else 'Colorless'}",
        f"Total Cards: {len(cards_expanded)}",
        "",
        "## Mana Curve",
        f"Average CMC: {avg_cmc:.1f}",
    ]

    # Add distribution
    if curve_distribution:
        dist_items = sorted(curve_distribution.items())
        dist_str = ", ".join(f"CMC {cmc}: {count}" for cmc, count in dist_items)
        context_parts.append(f"Distribution: {dist_str}")

    # Add curve issues
    if curve_issues:
        context_parts.append(f"Curve Issues: {', '.join(curve_issues)}")
    else:
        context_parts.append("Curve Issues: None - well balanced")

    context_parts.append("")

    # Add synergy summary
    context_parts.append("## Detected Synergies")
    if synergy_summary:
        context_parts.extend(synergy_summary)
    else:
        context_parts.append("No strong synergy patterns detected")

    context_parts.append("")

    # Add card list by type
    context_parts.append("## Cards by Type")

    # Group cards by type
    creatures = [dc for dc in mainboard_deck_cards if "Creature" in dc.card.type_line]
    spells = [
        dc
        for dc in mainboard_deck_cards
        if "Creature" not in dc.card.type_line and "Land" not in dc.card.type_line
    ]
    lands = [dc for dc in mainboard_deck_cards if "Land" in dc.card.type_line]

    if creatures:
        context_parts.append(f"Creatures ({sum(dc.quantity for dc in creatures)}):")
        for dc in creatures:
            context_parts.append(f"  - {dc.quantity}x {dc.card.name} ({dc.card.mana_cost})")

    if spells:
        context_parts.append(f"Spells ({sum(dc.quantity for dc in spells)}):")
        for dc in spells:
            context_parts.append(f"  - {dc.quantity}x {dc.card.name} ({dc.card.mana_cost})")

    if lands:
        context_parts.append(f"Lands ({sum(dc.quantity for dc in lands)}):")
        for dc in lands:
            context_parts.append(f"  - {dc.quantity}x {dc.card.name}")

    return "\n".join(context_parts)


async def _search_candidates(
    analysis: DeckAnalysis,
    card_repo: CardRepository,
    deps: AgentDependencies,
    deck: Deck,
    target_candidates: int = 75,
) -> list[Card]:
    """Search for candidate cards based on analysis criteria.

    Executes parallel database searches using asyncio.gather() and
    deduplicates results, excluding cards already in the deck.

    Args:
        analysis: DeckAnalysis with search criteria
        card_repo: CardRepository instance
        deps: Agent dependencies with format/games filters
        deck: Current deck (for exclusion and color filtering)
        target_candidates: Target number of candidates (default 75)

    Returns:
        Deduplicated list of candidate Cards (up to target_candidates)
    """
    # Build exclusion set from current deck cards
    existing_card_ids = {dc.card.id for dc in deck.deck_cards}

    # Get deck colors for color identity filter
    if deck.color_identity:
        deck_colors = deck.color_identity
    else:
        deck_colors = list({c for dc in deck.deck_cards for c in (dc.card.color_identity or [])})

    # Get filters from deps
    format_filter = deps.format_filter
    games_filter = deps.games_filter

    logger.debug(
        "Search filters: format=%s, games=%s, colors=%s",
        format_filter,
        games_filter,
        deck_colors,
    )

    # Build search tasks from analysis criteria
    search_tasks = []
    for criteria in analysis.search_criteria:
        # Build search parameters
        search_kwargs: dict[str, Any] = {
            "format_filter": format_filter,
            "games": games_filter,
            "page": 1,
            "page_size": 30,  # Get 30 per search, aim for ~75-150 total
        }

        # Apply color identity filter (at_most = can only use deck's colors)
        if deck_colors:
            search_kwargs["colors"] = deck_colors
            search_kwargs["color_mode"] = "at_most"

        # Apply type filter if specified
        if criteria.search_types:
            # Pass types as list (search_advanced expects list[str])
            search_kwargs["types"] = criteria.search_types

        # Apply keyword filter if specified
        if criteria.search_keywords:
            # Pass keywords as list (search_advanced expects list[str])
            search_kwargs["keywords"] = criteria.search_keywords

        # Apply max CMC filter if specified
        if criteria.max_cmc is not None:
            search_kwargs["mana_value_max"] = criteria.max_cmc

        # Create coroutine for this search
        search_tasks.append(card_repo.search_advanced(**search_kwargs))

    # Execute all searches in parallel
    logger.info("Executing %d parallel searches for candidates", len(search_tasks))
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Flatten and deduplicate results
    seen_names: set[str] = set()
    unique_candidates: list[Card] = []

    for result in search_results:
        # Skip exceptions from individual searches
        if isinstance(result, BaseException):
            logger.warning("Search failed: %s", result)
            continue

        # Result is PaginatedResult[Card]
        for card in result.items:
            # Skip if already in deck
            if card.id in existing_card_ids:
                continue
            # Skip duplicates from different searches
            if card.name in seen_names:
                continue
            seen_names.add(card.name)
            unique_candidates.append(card)

    logger.info(
        "Found %d unique candidates after deduplication (target: %d)",
        len(unique_candidates),
        target_candidates,
    )

    return unique_candidates[:target_candidates]


def _format_candidates(candidates: list[Card]) -> str:
    """Format candidate cards for LLM consumption.

    Creates a compact representation of each card for the curation
    agent to evaluate.

    Args:
        candidates: List of candidate Card objects

    Returns:
        Formatted string with one card per line
    """
    lines = []
    for card in candidates:
        # Get display name (handles printed_name for OM1 cards)
        display_name = get_display_name(card)

        # Truncate oracle text to ~100 chars
        oracle_text = card.oracle_text or ""
        if len(oracle_text) > 100:
            oracle_text = oracle_text[:97] + "..."

        # Format: "Name (cost, type): oracle_text"
        cost = card.mana_cost or "-"
        type_line = card.type_line or "Unknown"
        lines.append(f"{display_name} ({cost}, {type_line}): {oracle_text}")

    return "\n".join(lines)


def _format_suggestions_output(
    suggestions: CardSuggestions,
    candidate_cards: dict[str, Card],
) -> str:
    """Format suggestions with card hover previews.

    Creates formatted output with visual card hover functionality
    for display in the chat interface.

    Args:
        suggestions: Curated card suggestions from curation agent
        candidate_cards: Name -> Card mapping for hover previews

    Returns:
        Formatted markdown string with hover-enabled card names
    """
    output_lines = ["## Card Suggestions for Your Deck", ""]

    for i, pick in enumerate(suggestions.top_picks, 1):
        card = candidate_cards.get(pick.card_name)
        if card:
            # Use hover wrapper for card image preview
            name_with_hover = wrap_card_name_with_hover(pick.card_name, card)
            # Invert priority display: priority 1 (highest) = 5 stars, priority 5 (lowest) = 1 star
            priority_stars = "⭐" * (6 - pick.priority)
            output_lines.append(f"{i}. **{name_with_hover}** (Priority: {priority_stars})")
            output_lines.append(f"   {pick.synergy_fit}")
            output_lines.append("")
        else:
            # Fallback for cards not in mapping (shouldn't happen)
            # Same inversion for consistency
            fallback_stars = "⭐" * (6 - pick.priority)
            output_lines.append(f"{i}. **{pick.card_name}** (Priority: {fallback_stars})")
            output_lines.append(f"   {pick.synergy_fit}")
            output_lines.append("")

    output_lines.append(f"**Strategy:** {suggestions.overall_strategy}")

    return "\n".join(output_lines)


# =============================================================================
# Main Tool Function (AC1, AC7, AC10)
# =============================================================================


async def suggest_synergy_cards(
    ctx: RunContext[AgentDependencies],
    user_request: str | None = None,
) -> str | dict[str, Any]:
    """Suggest cards that synergize with the current deck using LLM-hybrid analysis.

    This tool implements a 3-stage workflow:
    1. Analysis Stage: LLM agent analyzes deck composition and generates search criteria
    2. Search Stage: Parallel database searches retrieve 50-150 candidate cards
    3. Curation Stage: LLM agent evaluates candidates and selects best 5-7 with explanations

    Performance targets:
    - Total latency: < 10 seconds for typical 60-card deck
    - Stage 1 (analysis): < 5 seconds
    - Stage 2 (search): < 1 second
    - Stage 3 (curation): < 7 seconds
    - Token usage: < 20,000 per request

    Args:
        ctx: RunContext with AgentDependencies
        user_request: Optional user-specified focus area for suggestions (e.g., "removal",
            "card draw", "tribal support"). When provided, the analysis and curation stages
            will prioritize cards matching this request while still considering deck synergies.
            If None or empty string, suggestions are based purely on detected synergies.

    Returns:
        When successful: dict with keys:
            - has_suggestions: bool (True)
            - suggested_cards: list[Card] (top 5-7 cards for UI buttons)
            - formatted_text: str (formatted suggestions with hover previews)
        When no deck/empty deck: str (error message)
        When analysis fails: str (error message with guidance)

    Raises:
        No exceptions raised - all errors return user-friendly messages
    """
    # Normalize empty string to None (AC5)
    if user_request is not None and user_request.strip() == "":
        user_request = None
    deps = ctx.deps

    # Check for active deck
    if not deps.active_deck:
        return "No active deck to analyze. Use create_deck() or load_deck() first."

    deck = deps.active_deck

    # Get mainboard cards
    mainboard_cards = [dc for dc in deck.deck_cards if not dc.sideboard]

    if not mainboard_cards:
        return f"Deck '{deck.name}' is empty. Add cards before requesting suggestions."

    if len(mainboard_cards) < 5:
        return (
            f"Deck '{deck.name}' only has {len(mainboard_cards)} cards. "
            "Add more cards (at least 5) for meaningful suggestions."
        )

    logger.info(
        "Starting synergy suggestion workflow for deck '%s' (%d cards)",
        deck.name,
        len(mainboard_cards),
    )

    try:
        # Create LLM agents
        analysis_agent, curation_agent = _create_suggestion_agents()

        # Stage 1: Analyze deck
        logger.info("Stage 1: Analyzing deck composition")
        deck_context = _build_deck_context(deck)

        # Build analysis prompt with optional user request focus
        analysis_prompt_parts = [
            "Analyze this deck and generate search criteria for card suggestions:\n",
            deck_context,
        ]

        if user_request:
            analysis_prompt_parts.insert(
                1,
                f"\nUSER REQUEST: {user_request}\n"
                "Focus your search criteria on cards that address this request while still\n"
                "considering the deck's overall composition and synergy needs.\n",
            )

        analysis_prompt = "\n".join(analysis_prompt_parts)
        analysis_result = await analysis_agent.run(analysis_prompt)
        analysis = analysis_result.output

        logger.info(
            "Analysis complete: primary_synergy='%s', criteria_count=%d",
            analysis.primary_synergy,
            len(analysis.search_criteria),
        )

        # Stage 2: Search for candidates
        logger.info("Stage 2: Searching for candidate cards")
        candidates = await _search_candidates(
            analysis=analysis,
            card_repo=deps.card_repository,
            deps=deps,
            deck=deck,
            target_candidates=75,
        )

        if not candidates:
            format_note = f" for {deps.format_filter}" if deps.format_filter else ""
            games_note = f" on {', '.join(deps.games_filter)}" if deps.games_filter else ""
            return (
                f"No candidate cards found{format_note}{games_note}. "
                f"Try adjusting your deck's colors or changing the format/games filter."
            )

        logger.info("Found %d candidate cards", len(candidates))

        # Stage 3: Curate suggestions
        logger.info("Stage 3: Curating top suggestions")
        candidates_text = _format_candidates(candidates)

        # Build name -> Card mapping for later use
        candidate_map = {card.name: card for card in candidates}

        # Build curation prompt with optional user request priority
        curation_prompt_parts = [
            f"Deck analysis:\n"
            f"- Primary synergy: {analysis.primary_synergy}\n"
            f"- Reasoning: {analysis.reasoning}\n",
        ]

        if user_request:
            curation_prompt_parts.append(
                f"\nUSER PRIORITY: {user_request}\n"
                "When selecting your top picks, prioritize cards that best address the user's\n"
                "specific request while maintaining synergy with the deck.\n"
            )

        curation_prompt_parts.append(
            f"\nSelect the best 5-7 cards from these candidates:\n\n{candidates_text}"
        )

        curation_prompt = "".join(curation_prompt_parts)

        curation_result = await curation_agent.run(curation_prompt)
        suggestions = curation_result.output

        logger.info(
            "Curation complete: %d suggestions selected",
            len(suggestions.top_picks),
        )

        # Validate suggestions against candidate list (hallucination prevention - AC6)
        valid_picks = []
        invalid_picks = []
        for pick in suggestions.top_picks:
            if pick.card_name in candidate_map:
                valid_picks.append(pick)
            else:
                invalid_picks.append(pick.card_name)
                logger.warning("Invalid suggestion (hallucination): '%s'", pick.card_name)

        # Fallback if too many invalid suggestions
        if len(valid_picks) < 3:
            logger.warning(
                "Too many invalid suggestions (%d valid, %d invalid). Using fallback.",
                len(valid_picks),
                len(invalid_picks),
            )
            # Sort candidates by mana value and take top 5
            sorted_candidates = sorted(candidates, key=lambda c: c.cmc)[:5]
            valid_picks = [
                CuratedCard(
                    card_name=card.name,
                    synergy_fit=f"Fits deck's color identity and mana curve (CMC {card.cmc:.0f})",
                    priority=i + 1,
                )
                for i, card in enumerate(sorted_candidates)
            ]
            suggestions = CardSuggestions(
                top_picks=valid_picks,
                overall_strategy=(
                    "These cards were selected based on mana curve fit and color identity. "
                    "Consider your deck's specific synergies when deciding which to add."
                ),
            )
        else:
            # Update suggestions with only valid picks
            suggestions = CardSuggestions(
                top_picks=valid_picks[:7],  # Limit to 7
                overall_strategy=suggestions.overall_strategy,
            )

        # Build suggested cards list for UI buttons
        suggested_cards = [
            candidate_map[pick.card_name]
            for pick in suggestions.top_picks
            if pick.card_name in candidate_map
        ]

        # Format output with hover previews
        formatted_text = _format_suggestions_output(suggestions, candidate_map)

        logger.info("Synergy suggestion workflow complete")

        # Return structured signal for UI handling (AC7)
        return {
            "has_suggestions": True,
            "suggested_cards": suggested_cards,
            "formatted_text": formatted_text,
        }

    except Exception as e:
        logger.error(
            "Synergy suggestion failed for session %s: %s",
            deps.session_id,
            e,
            exc_info=True,
        )
        return (
            f"Unable to generate suggestions: {e}\n\n"
            "This may be due to a temporary issue. Please try again, "
            "or try simplifying your deck if the problem persists."
        )

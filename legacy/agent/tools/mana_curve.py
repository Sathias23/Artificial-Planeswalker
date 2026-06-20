"""Mana curve analysis tool for agent."""

import logging

from pydantic_ai import RunContext

from legacy.agent.dependencies import AgentDependencies
from src.logic.mana_curve import analyze_mana_curve

logger = logging.getLogger(__name__)


async def analyze_deck_mana_curve(ctx: RunContext[AgentDependencies]) -> str:
    """Analyze the mana curve of the currently active deck.

    This tool provides insights into:
    - CMC distribution (how many cards at each mana cost)
    - Land ratio and mana base health
    - Turn-by-turn playability analysis
    - Average CMC and curve shape
    - Potential issues (mana flood/screw risk, curve gaps, top-heavy)
    - Specific recommendations for improvement

    Returns:
        Formatted analysis report with distribution, issues, and recommendations

    Raises:
        ValueError: If no deck is currently active or deck is empty
    """
    deps = ctx.deps

    # Check for active deck
    if not deps.active_deck:
        return "No active deck to analyze. Use create_deck() or load_deck() first."

    # Use cached active deck (already loaded with cards)
    deck = deps.active_deck

    # Get all mainboard cards (expanded by quantity)
    all_cards = []
    for deck_card in deck.deck_cards:
        # Skip sideboard cards
        if deck_card.sideboard:
            continue
        # Expand each card by its quantity
        for _ in range(deck_card.quantity):
            all_cards.append(deck_card.card)

    if not all_cards:
        return f"Deck '{deck.name}' is empty. Add cards before analyzing mana curve."

    # Perform analysis
    try:
        analysis = analyze_mana_curve(all_cards)
    except ValueError as e:
        logger.error(f"Mana curve analysis failed: {e}")
        return f"Analysis failed: {e}"

    # Format results for display
    report_lines = [
        f"## Mana Curve Analysis: {deck.name}",
        "",
        f"**Total Cards:** {len(all_cards)} "
        f"({analysis.total_spells} spells, {analysis.total_lands} lands)",
        f"**Land Ratio:** {analysis.land_ratio:.1f}%",
        f"**Average CMC:** {analysis.average_cmc:.2f}",
        "",
        "### CMC Distribution",
    ]

    # Sort distribution by CMC for display
    sorted_cmcs = sorted(analysis.distribution.keys())
    for cmc in sorted_cmcs:
        count = analysis.distribution[cmc]
        bar = "█" * count
        report_lines.append(f"CMC {cmc}: {count:2d} {bar}")

    # Playable cards by turn
    report_lines.extend(
        [
            "",
            "### Playable Cards by Turn (on the play)",
        ]
    )
    for turn in range(1, 8):
        playable = analysis.playable_cards_by_turn.get(turn, 0)
        report_lines.append(f"Turn {turn}: {playable} cards")

    # Issues section
    if analysis.issues:
        report_lines.extend(
            [
                "",
                "### Issues Detected",
            ]
        )
        for issue in analysis.issues:
            report_lines.append(f"- {issue}")

    # Recommendations section
    report_lines.extend(
        [
            "",
            "### Recommendations",
        ]
    )
    for rec in analysis.recommendations:
        report_lines.append(f"- {rec}")

    return "\n".join(report_lines)

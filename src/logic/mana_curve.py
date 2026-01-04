"""Mana curve analysis for deck optimization.

This module analyzes mana curves to identify distribution issues like
mana flood/screw risks, turn-by-turn playability, and provides recommendations.
"""

from dataclasses import dataclass
from typing import Literal

from src.data.schemas import Card


@dataclass
class CurveFeedback:
    """Contextual feedback for a single card addition to a deck.

    Used to provide real-time guidance when users add cards to their decks,
    balancing helpfulness with brevity to avoid feedback fatigue.

    Attributes:
        message: Human-readable feedback text in conversational coaching tone
        feedback_type: Classification of feedback (positive, warning, neutral)
        triggered_by: Reason for feedback (e.g., "top_heavy", "early_plays_added")
        should_display: Whether throttling logic says to show this feedback
    """

    message: str
    feedback_type: Literal["positive", "warning", "neutral"]
    triggered_by: str
    should_display: bool


@dataclass
class ManaCurveAnalysis:
    """Analysis results for a deck's mana curve.

    Attributes:
        distribution: CMC → card count mapping
        total_lands: Number of land cards
        total_spells: Number of spell cards
        average_cmc: Mean CMC of all non-land spells
        playable_cards_by_turn: Turn → count of cards playable on that turn
        land_ratio: Percentage of deck that is lands
        issues: List of detected issues (flood/screw risk, gaps)
        recommendations: Suggested improvements
    """

    distribution: dict[int, int]
    total_lands: int
    total_spells: int
    average_cmc: float
    playable_cards_by_turn: dict[int, int]
    land_ratio: float
    issues: list[str]
    recommendations: list[str]


def analyze_mana_curve(cards: list[Card]) -> ManaCurveAnalysis:
    """Analyze the mana curve of a deck.

    Args:
        cards: List of cards in the deck (includes duplicates for quantity)

    Returns:
        ManaCurveAnalysis with distribution, issues, and recommendations

    Raises:
        ValueError: If cards list is empty
    """
    if not cards:
        raise ValueError("Cannot analyze mana curve of empty deck")

    # Separate lands from spells
    lands = [c for c in cards if c.type_line and "Land" in c.type_line]
    spells = [c for c in cards if c not in lands]

    total_lands = len(lands)
    total_spells = len(spells)
    total_cards = total_lands + total_spells

    # Build CMC distribution
    distribution: dict[int, int] = {}
    cmc_sum = 0

    for spell in spells:
        cmc = int(spell.cmc) if spell.cmc is not None else 0
        distribution[cmc] = distribution.get(cmc, 0) + 1
        cmc_sum += cmc

    # Calculate average CMC (excluding lands)
    average_cmc = cmc_sum / total_spells if total_spells > 0 else 0.0

    # Calculate playable cards per turn (assuming 1 land/turn on the play)
    playable_by_turn: dict[int, int] = {}
    for turn in range(1, 8):  # Analyze turns 1-7
        playable_count = sum(count for cmc, count in distribution.items() if cmc <= turn)
        playable_by_turn[turn] = playable_count

    # Calculate land ratio
    land_ratio = (total_lands / total_cards * 100) if total_cards > 0 else 0.0

    # Detect issues and generate recommendations
    issues = _detect_issues(
        distribution, total_lands, total_spells, total_cards, average_cmc, land_ratio
    )
    recommendations = _generate_recommendations(
        distribution, total_lands, total_spells, average_cmc, land_ratio, issues
    )

    return ManaCurveAnalysis(
        distribution=distribution,
        total_lands=total_lands,
        total_spells=total_spells,
        average_cmc=average_cmc,
        playable_cards_by_turn=playable_by_turn,
        land_ratio=land_ratio,
        issues=issues,
        recommendations=recommendations,
    )


def _detect_issues(
    distribution: dict[int, int],
    total_lands: int,
    total_spells: int,
    total_cards: int,
    average_cmc: float,
    land_ratio: float,
) -> list[str]:
    """Detect mana curve issues.

    Args:
        distribution: CMC → count mapping
        total_lands: Number of lands
        total_spells: Number of spells
        total_cards: Total cards in deck
        average_cmc: Average CMC of spells
        land_ratio: Percentage of lands

    Returns:
        List of issue descriptions
    """
    issues = []

    # Mana screw risk (too few lands)
    if land_ratio < 35.0:
        issues.append(f"Mana screw risk: Only {land_ratio:.1f}% lands (typical decks run 38-42%)")

    # Mana flood risk (too many lands)
    if land_ratio > 45.0:
        issues.append(f"Mana flood risk: {land_ratio:.1f}% lands (typical decks run 38-42%)")

    # High average CMC with normal land count
    if average_cmc > 3.5 and land_ratio < 40.0:
        issues.append(f"High average CMC ({average_cmc:.1f}) may need more lands or mana ramp")

    # Curve gaps (missing CMC slots between 1-4)
    early_cmcs = [1, 2, 3, 4]
    missing_cmcs = [cmc for cmc in early_cmcs if distribution.get(cmc, 0) == 0]
    if len(missing_cmcs) >= 2:
        cmc_str = ", ".join(str(c) for c in missing_cmcs)
        issues.append(f"Curve gaps at CMC {cmc_str} may cause early-game weakness")

    # Top-heavy curve (too many high-CMC spells)
    high_cmc_count = sum(count for cmc, count in distribution.items() if cmc >= 5)
    if total_spells > 0:
        high_cmc_ratio = high_cmc_count / total_spells
        if high_cmc_ratio > 0.25:  # More than 25% at 5+ CMC
            issues.append(f"Top-heavy curve: {high_cmc_ratio * 100:.1f}% of spells cost 5+ mana")

    # No early plays (0-1 cards at CMC 1-2)
    early_count = distribution.get(1, 0) + distribution.get(2, 0)
    if early_count <= 1:
        issues.append("Very few early plays (CMC 1-2) may cause slow starts")

    return issues


def _generate_recommendations(
    distribution: dict[int, int],
    total_lands: int,
    total_spells: int,
    average_cmc: float,
    land_ratio: float,
    issues: list[str],
) -> list[str]:
    """Generate recommendations based on detected issues.

    Args:
        distribution: CMC → count mapping
        total_lands: Number of lands
        total_spells: Number of spells
        average_cmc: Average CMC of spells
        land_ratio: Percentage of lands
        issues: List of detected issues

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Land count recommendations
    if land_ratio < 35.0:
        target_lands = int((total_lands + total_spells) * 0.40)
        to_add = target_lands - total_lands
        recommendations.append(f"Add ~{to_add} lands (target: {target_lands} lands)")
    elif land_ratio > 45.0:
        target_lands = int((total_lands + total_spells) * 0.40)
        to_remove = total_lands - target_lands
        recommendations.append(f"Remove ~{to_remove} lands (target: {target_lands} lands)")

    # High CMC recommendations
    if average_cmc > 3.5 and land_ratio < 40.0:
        recommendations.append(
            "High average CMC with current land count may benefit from mana acceleration"
        )

    # Curve gap recommendations
    early_cmcs = [1, 2, 3, 4]
    missing_cmcs = [cmc for cmc in early_cmcs if distribution.get(cmc, 0) == 0]
    if len(missing_cmcs) >= 2:
        recommendations.append(f"Curve has gaps at CMC {', '.join(str(c) for c in missing_cmcs)}")

    # Top-heavy recommendations
    high_cmc_count = sum(count for cmc, count in distribution.items() if cmc >= 5)
    if total_spells > 0:
        high_cmc_ratio = high_cmc_count / total_spells
        if high_cmc_ratio > 0.25:
            recommendations.append("Deck has high concentration of expensive spells (5+ CMC)")

    # Early play recommendations
    early_count = distribution.get(1, 0) + distribution.get(2, 0)
    if early_count <= 1:
        recommendations.append("Deck currently has very few early plays (1-2 CMC)")

    # If no issues, provide positive feedback
    if not issues:
        recommendations.append("Mana curve looks well-balanced! No major adjustments needed.")

    return recommendations


def generate_contextual_feedback(deck_cards: list[Card], added_card: Card) -> CurveFeedback | None:
    """Generate contextual mana curve feedback when a card is added to a deck.

    This function implements throttling logic to avoid feedback fatigue while providing
    helpful guidance at critical moments during deck construction. Feedback considers
    the inferred deck archetype and generates conversational, coaching-style messages.

    Args:
        deck_cards: List of all cards currently in the deck (includes the newly added card)
        added_card: The card that was just added (triggers feedback evaluation)

    Returns:
        CurveFeedback if feedback should be displayed, None if throttled

    Throttling Strategy:
        - Deck has < 5 cards (early construction) → Always give feedback
        - Any CMC bucket changes by > 15% of total deck → Give feedback
        - New curve problems detected → Give feedback
        - Otherwise → Skip feedback to avoid fatigue

    Examples:
        >>> cards = [card1_mana_1, card2_mana_1, card3_mana_2]
        >>> added = card1_mana_1
        >>> feedback = generate_contextual_feedback(cards, added)
        >>> feedback.feedback_type
        'positive'
        >>> feedback.message
        'Great addition! Strong early-game presence for an aggressive deck.'
    """
    # Early exit: Cannot provide feedback without cards
    if not deck_cards:
        return None

    # Separate lands from spells for analysis
    lands = [c for c in deck_cards if c.type_line and "Land" in c.type_line]
    spells = [c for c in deck_cards if c not in lands]

    total_cards = len(deck_cards)
    total_spells = len(spells)

    # Build current CMC distribution
    current_distribution: dict[int, int] = {}
    cmc_sum = 0

    for spell in spells:
        cmc = int(spell.cmc) if spell.cmc is not None else 0
        current_distribution[cmc] = current_distribution.get(cmc, 0) + 1
        cmc_sum += cmc

    # Calculate average CMC for archetype inference
    average_cmc = cmc_sum / total_spells if total_spells > 0 else 0.0

    # Infer deck archetype based on average CMC
    archetype = _infer_archetype(average_cmc)

    # THROTTLING LOGIC: Determine if we should provide feedback

    # Always provide feedback for first few cards (establishing curve)
    if total_cards < 5:
        return _generate_early_deck_feedback(added_card, total_cards, archetype)

    # Build distribution BEFORE the addition (for comparison)
    # Remove added card temporarily to see previous state
    previous_spells = [s for s in spells if s.id != added_card.id]
    previous_distribution: dict[int, int] = {}

    for spell in previous_spells:
        cmc = int(spell.cmc) if spell.cmc is not None else 0
        previous_distribution[cmc] = previous_distribution.get(cmc, 0) + 1

    # Check if curve distribution shifted significantly (> 15% in any bucket)
    added_cmc = int(added_card.cmc) if added_card.cmc is not None else 0
    previous_total = total_cards - 1
    previous_percentage = (
        (previous_distribution.get(added_cmc, 0) / previous_total * 100)
        if previous_total > 0
        else 0
    )  # noqa: E501
    current_percentage = current_distribution.get(added_cmc, 0) / total_cards * 100
    distribution_shift = abs(current_percentage - previous_percentage)

    # Detect curve problems AFTER addition
    has_top_heavy_problem = _is_top_heavy(current_distribution, total_spells)
    has_early_play_problem = _lacks_early_plays(current_distribution)

    # Trigger feedback if significant change or problem detected
    should_give_feedback = (
        distribution_shift > 15.0  # Significant shift in CMC distribution
        or has_top_heavy_problem  # Deck becoming top-heavy
        or has_early_play_problem  # Deck lacks early plays
    )

    if not should_give_feedback:
        return None  # Throttle feedback - change not significant enough

    # FEEDBACK GENERATION: Generate appropriate message based on context
    # WARNING: Warnings take priority over positive feedback

    # Check for warning scenarios first (higher priority)
    if has_top_heavy_problem:
        return _generate_top_heavy_warning(current_distribution, total_spells)

    if has_early_play_problem:
        return _generate_early_play_warning(current_distribution, total_spells)

    # Check for positive reinforcement scenarios
    if _is_good_addition(added_card, archetype, current_distribution, total_spells):
        return _generate_positive_feedback(added_card, archetype)

    # Neutral observation (balanced addition)
    return _generate_neutral_feedback(current_distribution)


def _infer_archetype(average_cmc: float) -> str:
    """Infer deck archetype from average CMC.

    Args:
        average_cmc: Mean CMC of all non-land spells in deck

    Returns:
        Archetype string: "aggro", "midrange", or "control"
    """
    if average_cmc <= 2.5:
        return "aggro"
    elif average_cmc <= 3.5:
        return "midrange"
    else:
        return "control"


def _is_top_heavy(distribution: dict[int, int], total_spells: int) -> bool:
    """Check if deck has too many high-CMC spells (top-heavy).

    Args:
        distribution: CMC → count mapping
        total_spells: Total number of non-land spells

    Returns:
        True if > 25% of spells cost 5+ mana
    """
    if total_spells == 0:
        return False

    high_cmc_count = sum(count for cmc, count in distribution.items() if cmc >= 5)
    high_cmc_ratio = high_cmc_count / total_spells
    return high_cmc_ratio > 0.25


def _lacks_early_plays(distribution: dict[int, int]) -> bool:
    """Check if deck has very few early plays (CMC 1-2).

    Args:
        distribution: CMC → count mapping

    Returns:
        True if deck has ≤ 3 cards at CMC 1-2
    """
    early_count = distribution.get(1, 0) + distribution.get(2, 0)
    return early_count <= 3


def _is_good_addition(
    added_card: Card, archetype: str, distribution: dict[int, int], total_spells: int
) -> bool:
    """Check if the added card is a good fit for the deck's archetype.

    Args:
        added_card: Card that was just added
        archetype: Inferred deck archetype ("aggro", "midrange", "control")
        distribution: Current CMC distribution
        total_spells: Total number of non-land spells

    Returns:
        True if card is beneficial for the archetype
    """
    added_cmc = int(added_card.cmc) if added_card.cmc is not None else 0

    # Aggro: Good addition if low CMC (1-2)
    if archetype == "aggro" and added_cmc <= 2:
        return True

    # Control: Good addition if high CMC finisher or early interaction
    if archetype == "control" and (added_cmc >= 5 or added_cmc <= 2):
        return True

    # Midrange: Good addition if fills 2-4 CMC curve
    if archetype == "midrange" and 2 <= added_cmc <= 4:
        return True

    return False


def _generate_early_deck_feedback(
    added_card: Card, total_cards: int, archetype: str
) -> CurveFeedback:
    """Generate feedback for early deck construction (< 5 cards).

    Args:
        added_card: Card that was just added
        total_cards: Total number of cards in deck
        archetype: Inferred deck archetype

    Returns:
        CurveFeedback with encouraging message
    """
    added_cmc = int(added_card.cmc) if added_card.cmc is not None else 0

    if added_cmc <= 2:
        message = (
            f"Great start! {added_card.name} provides early-game presence. "
            f"This could fit a {archetype} strategy."
        )
        return CurveFeedback(
            message=message,
            feedback_type="positive",
            triggered_by="early_deck_construction",
            should_display=True,
        )
    else:
        message = (
            f"Starting with {added_card.name} at {added_cmc} mana. "
            f"Early plays (1-3 mana) will help with consistency."
        )
        return CurveFeedback(
            message=message,
            feedback_type="neutral",
            triggered_by="early_deck_construction",
            should_display=True,
        )


def _generate_positive_feedback(added_card: Card, archetype: str) -> CurveFeedback:
    """Generate positive reinforcement feedback for good additions.

    Args:
        added_card: Card that was just added
        archetype: Inferred deck archetype

    Returns:
        CurveFeedback with positive message
    """
    added_cmc = int(added_card.cmc) if added_card.cmc is not None else 0

    # Archetype-specific positive messages
    if archetype == "aggro" and added_cmc <= 2:
        message = (
            f"Great addition! {added_card.name} provides strong early-game presence "
            f"for an aggressive deck."
        )
    elif archetype == "control" and added_cmc >= 5:
        message = (
            f"Strong finisher! {added_card.name} gives you a powerful late-game threat "
            f"for your control strategy."
        )
    elif archetype == "control" and added_cmc <= 2:
        message = (
            f"Nice! {added_card.name} provides early interaction to help you reach "
            f"the late game safely."
        )
    elif archetype == "midrange":
        message = f"Solid addition! {added_card.name} fits well into your midrange curve."
    else:
        message = f"Good choice! {added_card.name} fits your deck's strategy."

    return CurveFeedback(
        message=message,
        feedback_type="positive",
        triggered_by="good_archetype_fit",
        should_display=True,
    )


def _generate_top_heavy_warning(distribution: dict[int, int], total_spells: int) -> CurveFeedback:
    """Generate warning feedback for top-heavy curve.

    Args:
        distribution: CMC distribution
        total_spells: Total number of non-land spells

    Returns:
        CurveFeedback with warning message
    """
    high_cmc_count = sum(count for cmc, count in distribution.items() if cmc >= 5)
    high_cmc_ratio = high_cmc_count / total_spells if total_spells > 0 else 0
    percentage = high_cmc_ratio * 100

    message = (
        f"Deck is becoming top-heavy ({percentage:.0f}% at 5+ mana). "
        f"More 1-3 mana plays would improve early-game consistency."
    )

    return CurveFeedback(
        message=message,
        feedback_type="warning",
        triggered_by="top_heavy",
        should_display=True,
    )


def _generate_early_play_warning(distribution: dict[int, int], total_spells: int) -> CurveFeedback:
    """Generate warning feedback for lack of early plays.

    Args:
        distribution: CMC distribution
        total_spells: Total number of non-land spells

    Returns:
        CurveFeedback with warning message
    """
    early_count = distribution.get(1, 0) + distribution.get(2, 0)
    early_ratio = early_count / total_spells if total_spells > 0 else 0
    percentage = early_ratio * 100

    message = (
        f"Deck has very few early plays ({percentage:.0f}% at ≤ 2 mana). "
        f"Low-cost cards would help avoid slow starts."
    )

    return CurveFeedback(
        message=message,
        feedback_type="warning",
        triggered_by="lacks_early_plays",
        should_display=True,
    )


def _generate_neutral_feedback(distribution: dict[int, int]) -> CurveFeedback:
    """Generate neutral observation feedback for balanced additions.

    Args:
        distribution: CMC distribution

    Returns:
        CurveFeedback with neutral message
    """
    # Find the primary CMC range (where most cards are)
    max_cmc = max(distribution.keys()) if distribution else 0
    primary_range_start = 2
    primary_range_end = 4

    if max_cmc >= 5:
        primary_range_end = 4
    elif max_cmc <= 2:
        primary_range_end = 2

    message = f"Curve remains balanced across {primary_range_start}-{primary_range_end} mana."

    return CurveFeedback(
        message=message,
        feedback_type="neutral",
        triggered_by="balanced_addition",
        should_display=True,
    )

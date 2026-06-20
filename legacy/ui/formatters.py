"""Formatting functions for displaying MTG card data in Chainlit chat interface.

This module provides functions to convert Card Pydantic models into formatted
text displays suitable for the Chainlit chat interface, including proper
mana symbol representation, structured layouts, and result limiting.

Chainlit integration is isolated to this module to maintain clean separation
between UI and agent layers. Image display uses Chainlit's Image element API.
"""

import html
import os
import re
from typing import TYPE_CHECKING, Any

from src.data.schemas import Card

if TYPE_CHECKING:
    import chainlit as cl

    from src.data.schemas.deck import Deck, DeckCard
    from src.logic.synergy import SynergyAnalysis


def _use_visual_symbols() -> bool:
    """Check if visual mana symbols are enabled via environment variable.

    Reads the VISUAL_MANA_SYMBOLS environment variable. Defaults to True
    if not set or if value cannot be parsed.

    Returns:
        bool: True if visual symbols should be used, False for text notation
    """
    value = os.getenv("VISUAL_MANA_SYMBOLS", "true").lower()
    return value not in ("false", "0", "no", "off")


def _use_card_image_hover() -> bool:
    """Check if card image hover preview is enabled via environment variable.

    Reads the CARD_IMAGE_HOVER_ENABLED environment variable. Defaults to True
    if not set or if value cannot be parsed.

    Returns:
        bool: True if card image hover should be used, False for plain text
    """
    value = os.getenv("CARD_IMAGE_HOVER_ENABLED", "true").lower()
    return value not in ("false", "0", "no", "off")


def get_display_name(card: Card) -> str:
    """Get the display name for a card, preferring printed_name when available.

    For OM1 "Universes Within" cards and other special printings, returns the
    printed name (e.g., "Nill, Vessel of Valgavoth") instead of the oracle name
    (e.g., "Tombstone, Career Criminal").

    This ensures users see the name as it appears on the physical/digital card
    rather than the canonical oracle name.

    Args:
        card: Card instance

    Returns:
        printed_name if available and non-empty, otherwise name

    Examples:
        >>> om1_card = Card(
        ...     name="Tombstone, Career Criminal",
        ...     printed_name="Nill, Vessel of Valgavoth"
        ... )
        >>> get_display_name(om1_card)
        "Nill, Vessel of Valgavoth"
        >>> normal_card = Card(name="Lightning Bolt", printed_name=None)
        >>> get_display_name(normal_card)
        "Lightning Bolt"
    """
    return card.printed_name if card.printed_name else card.name


def wrap_card_name_with_hover(card_name: str, card: Card | None = None) -> str:
    """Wrap card name with hover preview HTML if image available.

    Generates HTML span with hover functionality that displays the card image
    from Scryfall CDN on hover. Uses CSS custom property to set background image.

    Falls back to plain text (HTML-escaped) if:
    - Card instance not provided
    - Image URLs not available in card data
    - Feature flag CARD_IMAGE_HOVER_ENABLED is disabled

    Args:
        card_name: The display name of the card to wrap
        card: Optional Card instance with image_uris data

    Returns:
        HTML string with hover span or HTML-escaped plain text

    Examples:
        >>> wrap_card_name_with_hover("Lightning Bolt", lightning_bolt_card)
        '<span class="card-hover" style="--card-image-url: url(\\'https://...\\')">Lightning Bolt\
</span>'
        >>> wrap_card_name_with_hover("Lightning Bolt", None)
        'Lightning Bolt'  # HTML-escaped
        >>> wrap_card_name_with_hover("Lightning Bolt", card_without_images)
        'Lightning Bolt'  # HTML-escaped, no image available

    Notes:
        - Prefers "normal" size image (balanced quality and performance)
        - For dual-faced cards, uses front face image (card_faces[0])
        - Image URLs are from Scryfall CDN (authorized in Card.image_uris)
        - Feature toggle: CARD_IMAGE_HOVER_ENABLED environment variable
        - Requires custom CSS file: public/card-preview.css
    """
    # Check feature flag
    if not _use_card_image_hover():
        return html.escape(card_name)

    # Early return if no card data provided
    if card is None:
        return html.escape(card_name)

    # Try to get image URL from card data
    image_url = None

    if card.image_uris and "normal" in card.image_uris:
        # Single-faced card with root-level image
        image_url = card.image_uris["normal"]
    elif _has_card_faces(card):
        # Dual-faced card - try to get image from first face
        assert card.card_faces is not None  # Type guard for mypy
        first_face = card.card_faces[0]
        if "image_uris" in first_face and "normal" in first_face["image_uris"]:
            image_url = first_face["image_uris"]["normal"]

    # If no image URL found, return plain text
    if not image_url:
        return html.escape(card_name)

    # Generate HTML with hover functionality
    # Use CSS custom property to set background image URL
    # CSS file (public/card-preview.css) handles tooltip display on hover
    escaped_name = html.escape(card_name)
    escaped_url = html.escape(image_url, quote=True)

    # Add games availability as data attribute for tooltip display
    games_attr = ""
    if card.games:
        games_display = ", ".join(g.capitalize() for g in card.games)
        escaped_games = html.escape(games_display)
        games_attr = f' data-games="{escaped_games}"'

    return (
        f'<span class="card-hover" '
        f"style=\"--card-image-url: url('{escaped_url}')\"{games_attr}>"
        f"{escaped_name}</span>"
    )


def parse_mana_cost(mana_cost: str) -> list[str]:
    """Parse a mana cost string into individual symbol components.

    Extracts all symbols from Scryfall mana cost notation by finding
    all {X} patterns in the string.

    Args:
        mana_cost: Scryfall mana cost string (e.g., "{2}{R}{G}")

    Returns:
        List of symbol strings in order (e.g., ["{2}", "{R}", "{G}"])
        Returns empty list if mana_cost is empty or None

    Examples:
        >>> parse_mana_cost("{2}{R}{G}")
        ["{2}", "{R}", "{G}"]
        >>> parse_mana_cost("{W/U}")
        ["{W/U}"]
        >>> parse_mana_cost("")
        []
    """
    if not mana_cost:
        return []

    # Match all {X} patterns where X is any non-} characters
    pattern = r"\{[^}]+\}"
    symbols = re.findall(pattern, mana_cost)
    return symbols


def render_symbol_as_html(symbol: str) -> str:
    """Render a single mana symbol as HTML IMG tag.

    Looks up the symbol's SVG URL from the Scryfall symbol cache and
    generates an IMG tag with proper class and alt attributes for CSS targeting.

    Falls back to HTML-escaped text if the symbol is not found in the cache
    or cache not initialized.

    Args:
        symbol: Symbol notation (e.g., "{R}", "{2}", "{W/U}")

    Returns:
        HTML string with IMG tag or escaped text

    Examples:
        >>> render_symbol_as_html("{R}")
        '<img src="https://svgs.scryfall.io/card-symbols/R.svg" alt="{R}" class="mana-symbol" />'
        >>> render_symbol_as_html("{UNKNOWN}")
        '&lt;UNKNOWN&gt;'  # HTML-escaped fallback
    """
    from legacy.ui.symbols import get_symbol_svg_url_sync

    # Look up symbol SVG URL (sync version - cache must be pre-initialized)
    svg_url = get_symbol_svg_url_sync(symbol)

    if svg_url:
        # Simple IMG tag with class - styling handled by CSS file (mana-symbols.css)
        # The CSS targets images by:
        # 1. Class selector (.mana-symbol)
        # 2. Alt attribute pattern (alt^="{" and alt$="}")
        # 3. Src URL pattern (src*="scryfall.io/card-symbols")
        # Multiple selectors provide redundancy and specificity
        escaped_symbol = html.escape(symbol)
        return f'<img src="{svg_url}" alt="{escaped_symbol}" class="mana-symbol" />'
    else:
        # Fallback to HTML-escaped text
        return html.escape(symbol)


def format_mana_symbols(mana_cost: str, use_visual: bool | None = None) -> str:
    """Convert Scryfall mana cost notation to visual symbols or readable text.

    Renders mana costs as inline SVG images from Scryfall's CDN when use_visual=True.
    Falls back to text notation if visual rendering is disabled or fails.

    Handles all standard Magic mana symbols including:
    - Basic colors: {W}, {U}, {B}, {R}, {G}
    - Colorless: {C}
    - Generic: {0}, {1}, {2}, etc.
    - Hybrid: {W/U}, {2/R}, etc.
    - Phyrexian: {W/P}, {U/P}, etc.
    - Snow: {S}
    - X costs: {X}, {Y}, {Z}
    - Special: {T} (tap), {Q} (untap), {E} (energy)

    Args:
        mana_cost: Scryfall mana cost string (e.g., "{2}{R}{G}")
        use_visual: If True, render as HTML IMG tags; if False, return text.
                   If None (default), reads from VISUAL_MANA_SYMBOLS env var.

    Returns:
        HTML string with inline symbol images, or plain text if use_visual=False

    Examples:
        >>> format_mana_symbols("{1}{R}{G}", use_visual=True)
        '<img src="..." alt="{1}" class="mana-symbol" /><img src="..." alt="{R}" ...>'
        >>> format_mana_symbols("{1}{R}{G}", use_visual=False)
        "{1}{R}{G}"
        >>> format_mana_symbols("")
        ""

    Notes:
        - Requires symbol cache to be initialized at app startup
        - Falls back to text if cache not initialized or symbol not found
        - Initialize cache by calling `await get_symbol_cache()` during app startup
        - Default behavior controlled by VISUAL_MANA_SYMBOLS environment variable
    """
    if not mana_cost:
        return ""

    # Use environment variable if not explicitly specified
    if use_visual is None:
        use_visual = _use_visual_symbols()

    if not use_visual:
        # Text fallback - return as-is
        return mana_cost

    try:
        # Parse mana cost into individual symbols
        symbols = parse_mana_cost(mana_cost)

        if not symbols:
            # No symbols found - return text fallback
            return html.escape(mana_cost)

        # Render each symbol as HTML
        html_parts = []
        for symbol in symbols:
            symbol_html = render_symbol_as_html(symbol)
            html_parts.append(symbol_html)

        return "".join(html_parts)

    except Exception as e:
        # Log error and fall back to text
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to render mana symbols for '{mana_cost}': {e}")
        return html.escape(mana_cost)


def render_oracle_text_symbols(oracle_text: str, use_visual: bool | None = None) -> str:
    """Render mana symbols in oracle text as visual images.

    Replaces all {X} symbol patterns in oracle text with inline SVG images
    while preserving line breaks and text formatting.

    Args:
        oracle_text: Card oracle text with inline symbols (e.g., "{T}: Add {R}")
        use_visual: If True, render symbols as IMG tags; if False, return text unchanged.
                   If None (default), reads from VISUAL_MANA_SYMBOLS env var.

    Returns:
        HTML string with symbols replaced by images, or plain text if use_visual=False

    Examples:
        >>> render_oracle_text_symbols("{T}: Add {R}", use_visual=True)
        '<img .../> Add <img .../>'
        >>> render_oracle_text_symbols("{T}: Add {R}", use_visual=False)
        "{T}: Add {R}"
        >>> render_oracle_text_symbols("Draw a card.")
        "Draw a card."

    Notes:
        - Line breaks are preserved in output
        - Text outside symbols is HTML-escaped for safety
        - Requires symbol cache initialized at app startup
        - Default behavior controlled by VISUAL_MANA_SYMBOLS environment variable
    """
    if not oracle_text:
        return ""

    # Use environment variable if not explicitly specified
    if use_visual is None:
        use_visual = _use_visual_symbols()

    if not use_visual:
        # Text fallback - return as-is
        return oracle_text

    try:
        # Find all symbols in text
        pattern = r"(\{[^}]+\})"
        parts = re.split(pattern, oracle_text)

        # Process each part - odd indices are symbols, even are text
        html_parts = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Plain text - escape HTML
                html_parts.append(html.escape(part))
            else:
                # Symbol - render as HTML
                symbol_html = render_symbol_as_html(part)
                html_parts.append(symbol_html)

        return "".join(html_parts)

    except Exception as e:
        # Log error and fall back to text
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to render symbols in oracle text: {e}")
        return html.escape(oracle_text)


def _has_card_faces(card: Card) -> bool:
    """Check if a card has multiple faces.

    Dual-faced cards (flip, transform, modal DFC, meld, split) store
    face-specific data in the card_faces array rather than at root level.

    Args:
        card: Card Pydantic schema instance

    Returns:
        True if card has card_faces data, False otherwise

    Examples:
        >>> single_faced = Card(name="Lightning Bolt", card_faces=None)
        >>> _has_card_faces(single_faced)
        False
        >>> dual_faced = Card(name="Delver // Aberration", card_faces=[{...}, {...}])
        >>> _has_card_faces(dual_faced)
        True
    """
    return card.card_faces is not None and len(card.card_faces) > 0


def _format_card_face(face: dict[str, Any], face_number: int) -> list[str]:
    """Format a single card face for display.

    Extracts and formats face-specific data (name, mana cost, type line,
    oracle text) for dual-faced cards.

    Args:
        face: Face object from card_faces array
        face_number: Face index (0 for front, 1 for back)

    Returns:
        List of formatted text lines for this face

    Examples:
        >>> face = {"name": "Delver of Secrets", "mana_cost": "{U}", ...}
        >>> lines = _format_card_face(face, 0)
        >>> lines[0]
        "**Front Face:**"
    """
    lines = []

    # Face label
    face_label = "Front Face" if face_number == 0 else "Back Face"
    lines.append(f"**{face_label}:**")

    # Face name (if different from combined name)
    face_name = face.get("name")
    if face_name:
        lines.append(f"{face_name}")

    # Mana cost (if present)
    mana_cost = face.get("mana_cost")
    if mana_cost:
        formatted_mana = format_mana_symbols(mana_cost)
        lines.append(f"Mana Cost: {formatted_mana}")

    # Type line
    type_line = face.get("type_line")
    if type_line:
        lines.append(f"*{type_line}*")

    # Oracle text (with visual symbol rendering)
    oracle_text = face.get("oracle_text")
    if oracle_text:
        lines.append("")  # Blank line for separation
        lines.append(render_oracle_text_symbols(oracle_text))

    return lines


def format_card_details(card: Card) -> str:
    """Format a single card with detailed information for display.

    Creates a structured display with:
    - Bold card name on first line
    - For dual-faced cards: "**Front Face:**" and "**Back Face:**" section labels
    - For each face (or root for single-faced): Mana cost (if present), Type line
      with emphasis, Oracle text with proper formatting
    - Color identity (once, for all faces)
    - Set information (once, for all faces)

    Supports both single-faced and dual-faced cards (flip, transform, modal DFC,
    meld, split layouts).

    Args:
        card: Card Pydantic schema instance

    Returns:
        Markdown-formatted string for Chainlit display

    Examples:
        >>> card = Card(name="Lightning Bolt", mana_cost="{R}", ...)
        >>> print(format_card_details(card))
        **Lightning Bolt**
        Mana Cost: {R}
        *Instant*
        ...
        >>> dual_card = Card(name="Delver // Aberration", card_faces=[...])
        >>> print(format_card_details(dual_card))
        **Delver of Secrets // Insectile Aberration**
        **Front Face:**
        ...
        **Back Face:**
        ...
    """
    lines = []

    # Card name (bold) with hover preview - use printed_name if available
    display_name = get_display_name(card)
    wrapped_name = wrap_card_name_with_hover(display_name, card)
    lines.append(f"<strong>{wrapped_name}</strong>")

    # Check if this is a dual-faced card
    if _has_card_faces(card):
        # Format each face separately
        assert card.card_faces is not None  # Type guard for mypy
        for i, face in enumerate(card.card_faces):
            if i > 0:
                lines.append("")  # Blank line between faces
            face_lines = _format_card_face(face, i)
            lines.extend(face_lines)
    else:
        # Single-faced card - use root-level fields
        # Mana cost (if present - lands typically don't have mana cost)
        if card.mana_cost:
            formatted_mana = format_mana_symbols(card.mana_cost)
            lines.append(f"Mana Cost: {formatted_mana}")

        # Type line (with emphasis)
        lines.append(f"*{card.type_line}*")

        # Oracle text (with visual symbol rendering and line breaks preserved)
        if card.oracle_text:
            lines.append("")  # Blank line for separation
            lines.append(render_oracle_text_symbols(card.oracle_text))

    # Shared data for all faces (shown once at end)
    # Color identity (if present)
    if card.colors:
        color_names = ", ".join(card.colors)
        lines.append("")  # Blank line
        lines.append(f"Colors: {color_names}")
    elif not card.mana_cost and not _has_card_faces(card):
        # Colorless indicator for single-faced cards without mana cost
        lines.append("")
        lines.append("Colorless")

    # Set information
    lines.append("")
    lines.append(f"Set: {card.set_name} ({card.set_code.upper()}) - {card.rarity.capitalize()}")

    # Games availability
    if card.games:
        games_display = ", ".join(game.capitalize() for game in card.games)
        lines.append(f"Available on: {games_display}")

    return "\n".join(lines)


def format_card_list(cards: list[Card], limit: int = 10) -> str:
    """Format a list of cards with consistent structure and truncation.

    Creates a numbered list showing:
    - Card name (for dual-faced: "Front Name // Back Name")
    - Mana cost
    - Type line (for dual-faced: may show both type lines)
    - Oracle text (truncated if long)

    Supports both single-faced and dual-faced cards (flip, transform, modal DFC,
    meld, split layouts).

    Limits results to prevent chat overflow and includes count of hidden cards.

    Args:
        cards: List of Card Pydantic schema instances
        limit: Maximum cards to display (default: 10, max: 15)

    Returns:
        Markdown-formatted numbered list string

    Examples:
        >>> cards = [card1, card2, card3]
        >>> print(format_card_list(cards, limit=2))
        1. **Lightning Bolt** {R} - *Instant*
           Lightning Bolt deals 3 damage to any target.
        2. **Delver of Secrets // Insectile Aberration** {U} - *Creature // Creature*
           Transform card with oracle text from both faces...
        ...and 1 more result
    """
    # Cap limit at 15 to prevent overflow
    limit = min(limit, 15)

    lines = []
    cards_to_show = cards[:limit]

    for i, card in enumerate(cards_to_show, start=1):
        # For dual-faced cards, card.name already contains "Front // Back"
        # Get mana cost (from root or first face)
        mana = ""
        if card.mana_cost:
            mana = format_mana_symbols(card.mana_cost)
        elif _has_card_faces(card):
            assert card.card_faces is not None  # Type guard for mypy
            if card.card_faces[0].get("mana_cost"):
                mana = format_mana_symbols(card.card_faces[0]["mana_cost"])

        mana_part = f" {mana}" if mana else ""

        # Games availability (compact format)
        games_part = ""
        if card.games:
            games_display = ", ".join(game.capitalize() for game in card.games)
            games_part = f" • {games_display}"

        # Format: "1. **Card Name** {cost} - *Type* • Paper, Arena" with hover preview
        # Use printed_name if available (e.g., OM1 cards)
        display_name = get_display_name(card)
        wrapped_name = wrap_card_name_with_hover(display_name, card)
        lines.append(
            f"{i}. <strong>{wrapped_name}</strong>{mana_part} - *{card.type_line}*{games_part}"
        )

        # Add oracle text (truncated if very long)
        # For dual-faced cards, combine oracle text from both faces
        oracle_text = ""
        if _has_card_faces(card):
            # Combine oracle text from all faces with separator
            assert card.card_faces is not None  # Type guard for mypy
            face_texts = []
            for face in card.card_faces:
                face_oracle = face.get("oracle_text", "")
                if face_oracle:
                    face_texts.append(face_oracle)
            oracle_text = " // ".join(face_texts) if face_texts else ""
        else:
            oracle_text = card.oracle_text or ""

        if oracle_text:
            # Truncate extremely long oracle text (keep first 150 chars)
            if len(oracle_text) > 150:
                oracle_text = oracle_text[:147] + "..."
            # Indent the oracle text for readability
            lines.append(f"   {oracle_text}")

    # Add "...and X more" message if truncated
    remaining = len(cards) - limit
    if remaining > 0:
        lines.append("")  # Blank line
        plural = "result" if remaining == 1 else "results"
        lines.append(f"...and {remaining} more {plural}")
        lines.append("_Try refining your search for more specific results._")

    return "\n".join(lines)


def format_card_with_image(card: Card) -> tuple[str, "cl.Image | None"]:
    """Format a card with image element for Chainlit display.

    Creates a formatted card display with an inline image element using
    Chainlit's Image API. For dual-faced cards, attempts to extract image
    from card_faces[0].image_uris when root image_uris is None.

    Falls back to text-only if image URIs are not available.

    Uses "normal" size image by default for best balance of quality and
    load time (~200-300KB). Images are fetched from Scryfall CDN.

    Args:
        card: Card Pydantic schema instance

    Returns:
        Tuple of (formatted_text, image_element):
        - formatted_text: Markdown-formatted card details
        - image_element: Chainlit Image element or None if no image available

    Examples:
        >>> text, image = format_card_with_image(lightning_bolt)
        >>> # In Chainlit message handler:
        >>> elements = [image] if image else []
        >>> await cl.Message(content=text, elements=elements).send()

    Notes:
        - For single-faced cards: Uses image_uris["normal"] at root level
        - For dual-faced cards: Uses card_faces[0]["image_uris"]["normal"]
        - Image display mode is "inline" to embed in conversation
        - Chainlit import is only done at runtime (TYPE_CHECKING guard)
    """
    # Get formatted text
    text = format_card_details(card)

    # Try to get image URL (check root level first, then card_faces)
    image_url = None

    if card.image_uris and "normal" in card.image_uris:
        # Single-faced card with root-level image
        image_url = card.image_uris["normal"]
    elif _has_card_faces(card):
        # Dual-faced card - try to get image from first face
        assert card.card_faces is not None  # Type guard for mypy
        first_face = card.card_faces[0]
        if "image_uris" in first_face and "normal" in first_face["image_uris"]:
            image_url = first_face["image_uris"]["normal"]

    # If no image URL found, return text only
    if not image_url:
        return text, None

    # Import Chainlit at runtime (avoids import in agent layer)
    import chainlit as cl

    # Create image element using "normal" size
    # Use printed_name if available for consistent display
    display_name = get_display_name(card)
    image = cl.Image(
        url=image_url,
        name=display_name,
        display="inline",  # Embed in conversation
    )

    return text, image


def _group_cards_by_type(deck_cards: list["DeckCard"]) -> dict[str, list["DeckCard"]]:
    """Group deck cards by card type (Creatures, Spells, Lands).

    Parses the type_line to categorize cards into three groups:
    - Creatures: Any card with "Creature" in type_line
    - Spells: Instants, Sorceries, Enchantments, Artifacts, Planeswalkers
    - Lands: Any card with "Land" in type_line

    Args:
        deck_cards: List of DeckCard instances

    Returns:
        Dictionary with keys "Creatures", "Spells", "Lands" containing
        DeckCard lists

    Examples:
        >>> cards = [creature_card, instant_card, land_card]
        >>> grouped = _group_cards_by_type(cards)
        >>> len(grouped["Creatures"])
        1
    """
    groups: dict[str, list[DeckCard]] = {
        "Creatures": [],
        "Spells": [],
        "Lands": [],
    }

    for deck_card in deck_cards:
        type_line = deck_card.card.type_line.lower()

        if "creature" in type_line:
            groups["Creatures"].append(deck_card)
        elif "land" in type_line:
            groups["Lands"].append(deck_card)
        else:
            # Everything else (Instants, Sorceries, Enchantments, Artifacts, Planeswalkers)
            groups["Spells"].append(deck_card)

    return groups


def _get_mana_value(deck_card: "DeckCard") -> float:
    """Extract mana value (CMC) from a deck card for sorting.

    Args:
        deck_card: DeckCard instance

    Returns:
        Mana value as float (0.0 if not present or card has multiple faces)

    Examples:
        >>> _get_mana_value(lightning_bolt)  # {R}
        1.0
        >>> _get_mana_value(basic_land)  # No mana cost
        0.0
    """
    # Use mana value (converted mana cost) from card
    return deck_card.card.cmc


def _format_card_entry(deck_card: "DeckCard") -> str:
    """Format a single deck card entry for display.

    Formats as: "Quantity - Card Name (Mana Cost) [Type Line]"
    Handles missing mana cost gracefully (shows as "-" for lands).

    Args:
        deck_card: DeckCard instance with card details

    Returns:
        Formatted card entry string

    Examples:
        >>> _format_card_entry(lightning_bolt_deck_card)
        "4 - Lightning Bolt ({R}) [Instant]"
        >>> _format_card_entry(mountain_deck_card)
        "10 - Mountain (-) [Basic Land — Mountain]"
    """
    quantity = deck_card.quantity
    # Use printed_name if available (e.g., OM1 cards in deck)
    display_name = get_display_name(deck_card.card)
    wrapped_name = wrap_card_name_with_hover(display_name, deck_card.card)
    mana_cost = deck_card.card.mana_cost or "-"
    type_line = deck_card.card.type_line

    # Format mana cost for display
    if mana_cost != "-":
        mana_display = format_mana_symbols(mana_cost)
    else:
        mana_display = "-"

    return f"{quantity} - {wrapped_name} ({mana_display}) [{type_line}]"


def _format_deck_summary(deck: "Deck") -> str:
    """Format deck summary header with name, format, strategy, and card counts.

    Creates header with:
    - Deck name and format
    - Strategy (if set)
    - Total mainboard count
    - Total sideboard count
    - Legality indicator for Standard (60+ cards)

    Args:
        deck: Deck instance with cards

    Returns:
        Formatted summary header string

    Examples:
        >>> summary = _format_deck_summary(mono_red_deck)
        >>> "Mono Red Aggro" in summary
        True
    """

    # Calculate card counts
    mainboard_count = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)
    sideboard_count = sum(dc.quantity for dc in deck.deck_cards if dc.sideboard)

    # Determine legality for Standard
    is_legal = mainboard_count >= 60
    legality_indicator = "✓ Legal for Standard" if is_legal else "⚠ Needs 60+ cards for Standard"

    format_display = deck.format.capitalize() if deck.format else "All"
    lines = [
        f"# {deck.name}",
        f"**Format:** {format_display}",
    ]

    # Add strategy if set
    if deck.strategy:
        # Truncate strategy to 200 chars for display
        strategy_display = deck.strategy
        if len(strategy_display) > 200:
            strategy_display = strategy_display[:197] + "..."
        lines.append(f"**Strategy:** {strategy_display}")

    lines.extend(
        [
            f"**Mainboard:** {mainboard_count} cards",
            f"**Sideboard:** {sideboard_count} cards",
            f"**Status:** {legality_indicator}",
            "",
        ]
    )

    return "\n".join(lines)


def format_deck_for_display(deck: "Deck", grouping: str = "type") -> str:
    """Format deck contents as readable markdown grouped by card type.

    Creates a formatted deck list with:
    - Header with deck name, format, card counts, legality status
    - Mainboard cards grouped by type (Creatures, Spells, Lands)
    - Cards sorted within groups by mana cost ascending, then alphabetically
    - Sideboard cards (if any) displayed separately with same grouping

    Args:
        deck: Deck instance with cards loaded
        grouping: Grouping strategy ("type" is default, others reserved for future)

    Returns:
        Markdown-formatted deck list string

    Examples:
        >>> formatted = format_deck_for_display(mono_red_deck)
        >>> "# Mono Red Aggro" in formatted
        True
        >>> "Creatures" in formatted
        True

    Notes:
        - UI-independent (returns plain markdown, no Chainlit imports)
        - Empty card groups are omitted from display
        - Sideboard displayed after mainboard with "## Sideboard" header
    """

    lines = []

    # Add deck summary header
    lines.append(_format_deck_summary(deck))

    # Separate mainboard and sideboard
    mainboard_cards = [dc for dc in deck.deck_cards if not dc.sideboard]
    sideboard_cards = [dc for dc in deck.deck_cards if dc.sideboard]

    # Check if deck is empty
    if not mainboard_cards and not sideboard_cards:
        lines.append("Your deck is empty. Add cards to get started.")
        return "\n".join(lines)

    # Format mainboard
    if mainboard_cards:
        lines.append("## Mainboard")
        lines.append("")

        # Group cards by type
        groups = _group_cards_by_type(mainboard_cards)

        # Display each group (only if non-empty)
        for group_name in ["Creatures", "Spells", "Lands"]:
            group_cards = groups[group_name]

            if not group_cards:
                continue  # Skip empty groups

            # Sort within group: mana value ascending, then alphabetically by name
            sorted_cards = sorted(
                group_cards,
                key=lambda dc: (_get_mana_value(dc), dc.card.name),
            )

            # Group header with count
            total_in_group = sum(dc.quantity for dc in sorted_cards)
            lines.append(f"### {group_name} ({total_in_group} cards)")
            lines.append("")

            # Format each card entry
            for deck_card in sorted_cards:
                lines.append(_format_card_entry(deck_card))

            lines.append("")  # Blank line after group

    # Format sideboard (if any)
    if sideboard_cards:
        lines.append("## Sideboard")
        lines.append("")

        # Group sideboard cards by type
        groups = _group_cards_by_type(sideboard_cards)

        # Display each group (only if non-empty)
        for group_name in ["Creatures", "Spells", "Lands"]:
            group_cards = groups[group_name]

            if not group_cards:
                continue  # Skip empty groups

            # Sort within group
            sorted_cards = sorted(
                group_cards,
                key=lambda dc: (_get_mana_value(dc), dc.card.name),
            )

            # Group header with count
            total_in_group = sum(dc.quantity for dc in sorted_cards)
            lines.append(f"### {group_name} ({total_in_group} cards)")
            lines.append("")

            # Format each card entry
            for deck_card in sorted_cards:
                lines.append(_format_card_entry(deck_card))

            lines.append("")  # Blank line after group

    return "\n".join(lines)


def format_deck_list(decks: list["Deck"]) -> str:
    """Format a list of decks for display.

    Creates a numbered list showing:
    - Deck name
    - Format
    - Total mainboard card count
    - Deck ID for reference

    Args:
        decks: List of Deck instances

    Returns:
        Markdown-formatted deck list string

    Examples:
        >>> decks = [deck1, deck2, deck3]
        >>> print(format_deck_list(decks))
        1. **Mono Red Aggro** (standard) - 60 cards - ID: deck-123
        2. **Control Deck** (standard) - 45 cards - ID: deck-456
    """
    if not decks:
        return "No decks found. Create a new deck to get started!"

    lines = ["**Your Decks:**", ""]

    for i, deck in enumerate(decks, start=1):
        # Calculate mainboard card count
        mainboard_count = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)

        # Format: "1. **Deck Name** (format) - X cards - ID: deck-id"
        lines.append(
            f"{i}. **{deck.name}** ({deck.format}) - {mainboard_count} cards - ID: `{deck.id}`"
        )

    return "\n".join(lines)


def format_deck_summary(deck: "Deck", card_count_mainboard: int, card_count_sideboard: int) -> str:
    """Format deck summary for load confirmation.

    Creates a formatted summary with:
    - Deck name and format
    - Strategy (if set)
    - Mainboard and sideboard card counts
    - Active deck confirmation message

    Args:
        deck: Deck instance
        card_count_mainboard: Total mainboard cards
        card_count_sideboard: Total sideboard cards

    Returns:
        Formatted summary string

    Examples:
        >>> summary = format_deck_summary(deck, 60, 15)
        >>> "Mono Red Aggro" in summary
        True
    """
    format_display = deck.format.capitalize() if deck.format else "All"
    lines = [
        f"**Loaded: {deck.name}**",
        f"Format: {format_display}",
    ]

    # Add strategy if set
    if deck.strategy:
        # Truncate strategy to 200 chars for display
        strategy_display = deck.strategy
        if len(strategy_display) > 200:
            strategy_display = strategy_display[:197] + "..."
        lines.append(f"Strategy: {strategy_display}")

    lines.extend(
        [
            f"Mainboard: {card_count_mainboard} cards",
            f"Sideboard: {card_count_sideboard} cards",
            "",
            "This deck is now active for building operations.",
        ]
    )

    return "\n".join(lines)


def format_synergies(analysis: "SynergyAnalysis", deck_name: str) -> str:
    """Format synergy analysis results as markdown for display.

    Args:
        analysis: SynergyAnalysis instance with detected patterns
        deck_name: Name of the analyzed deck

    Returns:
        Formatted markdown string with synergy report

    Examples:
        >>> from src.logic.synergy import SynergyAnalysis, SynergyPattern
        >>> pattern = SynergyPattern(
        ...     pattern_type="tribal",
        ...     subtype="Goblin",
        ...     affected_cards=["Goblin Guide", "Goblin King"],
        ...     explanation="12 Goblin creatures synergize with 2 tribal payoff cards",
        ...     strength="strong"
        ... )
        >>> analysis = SynergyAnalysis(synergies=[pattern], deck_cohesion="high")
        >>> result = format_synergies(analysis, "Goblin Deck")
        >>> "Goblin Deck" in result
        True
    """

    lines = [
        f"## Synergy Analysis: {deck_name}",
        "",
    ]

    # Overall deck cohesion
    cohesion_emoji = {
        "high": "✅",
        "moderate": "⚠️",
        "low": "❌",
    }
    emoji = cohesion_emoji.get(analysis.deck_cohesion, "")
    lines.append(
        f"**Deck Cohesion:** {emoji} {analysis.deck_cohesion.capitalize()} "
        f"({analysis.total_count} synergies detected)"
    )
    lines.append("")

    # If no synergies detected
    if not analysis.synergies:
        lines.extend(
            [
                "No significant synergies detected in this deck.",
                "",
                "This could mean:",
                "- The deck has diverse strategies without focused themes",
                "- There aren't enough cards of the same type/keyword/mechanic",
                "- Consider adding more cards that work together",
            ]
        )
        return "\n".join(lines)

    # Display each synergy pattern
    lines.append("### Detected Synergies")
    lines.append("")

    for i, synergy in enumerate(analysis.synergies, 1):
        # Strength indicator
        strength_emoji = {
            "strong": "🔥",
            "moderate": "👍",
            "weak": "💡",
        }
        strength_icon = strength_emoji.get(synergy.strength, "")

        # Pattern type label
        pattern_labels = {
            "tribal": "Tribal",
            "keyword": "Keyword",
            "mechanic_combo": "Mechanic Combo",
        }
        pattern_label = pattern_labels.get(synergy.pattern_type, synergy.pattern_type)

        # Format header
        lines.append(
            f"**{i}. {pattern_label}: {synergy.subtype.capitalize()}** "
            f"{strength_icon} ({synergy.strength})"
        )
        lines.append("")

        # Explanation
        lines.append(synergy.explanation)
        lines.append("")

        # Affected cards (limit to first 10 for display)
        card_count = len(synergy.affected_cards)
        display_cards = synergy.affected_cards[:10]

        lines.append(f"**Cards involved ({card_count} total):**")
        for card_name in display_cards:
            lines.append(f"- {card_name}")

        if card_count > 10:
            lines.append(f"- ... and {card_count - 10} more")

        lines.append("")

    return "\n".join(lines)


# Pagination helpers


def format_pagination_info(page: int, total_pages: int, total_count: int) -> str:
    """Format pagination information text.

    Args:
        page: Current page number (1-indexed)
        total_pages: Total number of pages
        total_count: Total number of results

    Returns:
        Formatted pagination info string
    """
    if total_count == 0:
        return "No results found"

    if total_pages == 1:
        return f"Showing all {total_count} results"

    return f"Showing page {page} of {total_pages} ({total_count} total results)"


def create_pagination_actions(page: int, total_pages: int) -> list["cl.Action"] | None:
    """Create pagination action buttons for card search results.

    Args:
        page: Current page number (1-indexed)
        total_pages: Total number of pages

    Returns:
        List of pagination actions, or None if single page
    """
    import chainlit as cl

    if total_pages <= 1:
        return None

    actions = []

    # Previous button (only if not on first page)
    if page > 1:
        actions.append(
            cl.Action(
                name="navigate_page",
                payload={"page": page - 1},
                label="← Previous",
                tooltip=f"Go to page {page - 1}",
            )
        )

    # Next button (only if not on last page)
    if page < total_pages:
        actions.append(
            cl.Action(
                name="navigate_page",
                payload={"page": page + 1},
                label="Next →",
                tooltip=f"Go to page {page + 1}",
            )
        )

    return actions if actions else None

"""Unit tests for card formatting functions."""

from unittest.mock import MagicMock, patch

import pytest

from src.data.schemas import Card
from legacy.ui.formatters import (
    _format_card_face,
    _has_card_faces,
    format_card_details,
    format_card_list,
    format_card_with_image,
    format_mana_symbols,
    wrap_card_name_with_hover,
)

# Test Fixtures


@pytest.fixture
def creature_card() -> Card:
    """Sample creature card for testing."""
    return Card(
        id="test-creature-123",
        name="Grizzly Bears",
        oracle_id="oracle-123",
        mana_cost="{1}{G}",
        cmc=2.0,
        type_line="Creature — Bear",
        oracle_text="",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="199",
        colors=["G"],
        color_identity=["G"],
        legalities={"standard": "not_legal", "modern": "legal"},
    )


@pytest.fixture
def instant_card() -> Card:
    """Sample instant card for testing."""
    return Card(
        id="test-instant-456",
        name="Lightning Bolt",
        oracle_id="oracle-456",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "not_legal", "modern": "legal"},
    )


@pytest.fixture
def land_card() -> Card:
    """Sample basic land card for testing."""
    return Card(
        id="test-land-789",
        name="Forest",
        oracle_id="oracle-789",
        mana_cost="",  # Lands have no mana cost
        cmc=0.0,
        type_line="Basic Land — Forest",
        oracle_text="{T}: Add {G}.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="295",
        colors=[],
        color_identity=["G"],
        legalities={"standard": "legal", "modern": "legal"},
    )


@pytest.fixture
def multicolor_card() -> Card:
    """Sample multicolor card for testing."""
    return Card(
        id="test-multi-abc",
        name="Fire // Ice",
        oracle_id="oracle-abc",
        mana_cost="{1}{R} // {1}{U}",
        cmc=2.0,
        type_line="Instant // Instant",
        oracle_text=(
            "Fire deals 2 damage divided as you choose among one or two targets.\n"
            "---\nTap target permanent. Draw a card."
        ),
        rarity="uncommon",
        set_code="MH2",
        set_name="Modern Horizons 2",
        collector_number="290",
        colors=["U", "R"],
        color_identity=["U", "R"],
        legalities={"standard": "not_legal", "modern": "legal"},
    )


@pytest.fixture
def transform_card() -> Card:
    """Sample transform (DFC) card for testing - Delver of Secrets."""
    return Card(
        id="test-transform-delver",
        name="Delver of Secrets // Insectile Aberration",
        oracle_id="oracle-delver",
        mana_cost="",  # Root level empty for dual-faced cards
        cmc=1.0,
        type_line="Creature — Human Wizard // Creature — Human Insect",
        oracle_text="",  # Root level empty - data in card_faces
        rarity="common",
        set_code="ISD",
        set_name="Innistrad",
        collector_number="51",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "not_legal", "modern": "legal"},
        card_faces=[
            {
                "name": "Delver of Secrets",
                "mana_cost": "{U}",
                "type_line": "Creature — Human Wizard",
                "oracle_text": (
                    "At the beginning of your upkeep, look at the top card of your library. "
                    "You may reveal that card. If an instant or sorcery card is revealed this way, "
                    "transform Delver of Secrets."
                ),
                "power": "1",
                "toughness": "1",
            },
            {
                "name": "Insectile Aberration",
                "type_line": "Creature — Human Insect",
                "oracle_text": "Flying",
                "power": "3",
                "toughness": "2",
            },
        ],
    )


@pytest.fixture
def modal_dfc_card() -> Card:
    """Sample modal DFC card for testing - Sephiroth (from bug report)."""
    return Card(
        id="test-modal-sephiroth",
        name="Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel",
        oracle_id="oracle-sephiroth",
        mana_cost="",  # Root level empty for dual-faced cards
        cmc=6.0,
        type_line="Legendary Creature — Human Soldier // Legendary Creature — Avatar Angel",
        oracle_text="",  # Root level empty - data in card_faces
        rarity="mythic",
        set_code="ACR",
        set_name="Universes Beyond: Final Fantasy",
        collector_number="134",
        colors=["B", "W"],
        color_identity=["B", "W"],
        legalities={"standard": "not_legal", "modern": "legal"},
        image_uris=None,  # Dual-faced cards have image_uris in card_faces
        card_faces=[
            {
                "name": "Sephiroth, Fabled SOLDIER",
                "mana_cost": "{2}{W}{W}{B}{B}",
                "type_line": "Legendary Creature — Human Soldier",
                "oracle_text": (
                    "Whenever Sephiroth, Fabled SOLDIER enters or attacks, "
                    "destroy up to one target creature or planeswalker. "
                    "If Sephiroth was cast, you may exile it and cast Sephiroth, One-Winged Angel."
                ),
                "power": "5",
                "toughness": "5",
                "image_uris": {
                    "small": "https://cards.scryfall.io/small/front/sephiroth-front.jpg",
                    "normal": "https://cards.scryfall.io/normal/front/sephiroth-front.jpg",
                    "large": "https://cards.scryfall.io/large/front/sephiroth-front.jpg",
                },
            },
            {
                "name": "Sephiroth, One-Winged Angel",
                "mana_cost": "{4}{W}{W}{B}{B}",
                "type_line": "Legendary Creature — Avatar Angel",
                "oracle_text": (
                    "Flying, vigilance, lifelink\n"
                    "When this creature transforms into Sephiroth, One-Winged Angel, "
                    "destroy all other creatures."
                ),
                "power": "7",
                "toughness": "7",
                "image_uris": {
                    "small": "https://cards.scryfall.io/small/back/sephiroth-back.jpg",
                    "normal": "https://cards.scryfall.io/normal/back/sephiroth-back.jpg",
                    "large": "https://cards.scryfall.io/large/back/sephiroth-back.jpg",
                },
            },
        ],
    )


# Test format_mana_symbols


def test_format_mana_symbols_basic_colors() -> None:
    """Test formatting of basic color mana symbols."""
    # Arrange
    mana_cost = "{1}{R}{G}"

    # Act
    result = format_mana_symbols(mana_cost)

    # Assert
    assert result == "{1}{R}{G}"


def test_format_mana_symbols_empty_string() -> None:
    """Test formatting of empty mana cost (lands)."""
    # Arrange
    mana_cost = ""

    # Act
    result = format_mana_symbols(mana_cost)

    # Assert
    assert result == ""


def test_format_mana_symbols_complex() -> None:
    """Test formatting of complex mana symbols."""
    # Arrange
    mana_cost = "{2}{W/U}{B/P}"

    # Act
    result = format_mana_symbols(mana_cost)

    # Assert
    # For MVP, we preserve Scryfall notation
    assert result == "{2}{W/U}{B/P}"


# Test format_card_details


def test_format_card_details_creature(creature_card: Card) -> None:
    """Test formatting creature card with all standard fields."""
    # Act
    result = format_card_details(creature_card)

    # Assert
    assert "**Grizzly Bears**" in result
    assert "Mana Cost: {1}{G}" in result
    assert "*Creature — Bear*" in result
    assert "Colors: G" in result
    assert "Limited Edition Alpha" in result


def test_format_card_details_instant_with_text(instant_card: Card) -> None:
    """Test formatting instant card with oracle text."""
    # Act
    result = format_card_details(instant_card)

    # Assert
    assert "**Lightning Bolt**" in result
    assert "Mana Cost: {R}" in result
    assert "*Instant*" in result
    assert "Lightning Bolt deals 3 damage to any target." in result
    assert "Colors: R" in result


def test_format_card_details_land_no_mana_cost(land_card: Card) -> None:
    """Test formatting land card without mana cost."""
    # Act
    result = format_card_details(land_card)

    # Assert
    assert "**Forest**" in result
    assert "Mana Cost:" not in result  # No mana cost for lands
    assert "*Basic Land — Forest*" in result
    assert "{T}: Add {G}." in result
    assert "Colorless" in result  # Indicates colorless when no colors


def test_format_card_details_multicolor(multicolor_card: Card) -> None:
    """Test formatting multicolor card."""
    # Act
    result = format_card_details(multicolor_card)

    # Assert
    assert "**Fire // Ice**" in result
    assert "Colors: U, R" in result
    assert "Instant // Instant" in result


def test_format_card_details_contains_set_info(instant_card: Card) -> None:
    """Test that card details include set information."""
    # Act
    result = format_card_details(instant_card)

    # Assert
    assert "Set: Limited Edition Alpha (LEA)" in result
    assert "Common" in result


# Test format_card_list


def test_format_card_list_single_card(instant_card: Card) -> None:
    """Test formatting a list with single card."""
    # Arrange
    cards = [instant_card]

    # Act
    result = format_card_list(cards)

    # Assert
    assert "1. **Lightning Bolt** {R} - *Instant*" in result
    assert "Lightning Bolt deals 3 damage to any target." in result
    assert "...and" not in result  # No truncation message


def test_format_card_list_multiple_cards_under_limit(
    instant_card: Card, creature_card: Card, land_card: Card
) -> None:
    """Test formatting list with cards under the default limit."""
    # Arrange
    cards = [instant_card, creature_card, land_card]

    # Act
    result = format_card_list(cards)

    # Assert
    assert "1. **Lightning Bolt** {R} - *Instant*" in result
    assert "Lightning Bolt deals 3 damage to any target." in result
    assert "2. **Grizzly Bears** {1}{G} - *Creature — Bear*" in result
    # Creature has empty oracle text in fixture, so no oracle text line
    assert "3. **Forest**" in result
    assert "*Basic Land — Forest*" in result
    assert "{T}: Add {G}." in result  # Land oracle text
    assert "...and" not in result


def test_format_card_list_truncation_at_limit(instant_card: Card) -> None:
    """Test that card list truncates at specified limit."""
    # Arrange
    cards = [instant_card] * 15  # 15 identical cards
    limit = 10

    # Act
    result = format_card_list(cards, limit=limit)

    # Assert
    lines = result.split("\n")
    numbered_lines = [line for line in lines if line and line[0].isdigit()]
    assert len(numbered_lines) == 10  # Only 10 cards shown
    assert "...and 5 more results" in result
    assert "Try refining your search" in result


def test_format_card_list_max_limit_enforced(instant_card: Card) -> None:
    """Test that card list enforces maximum limit of 15."""
    # Arrange
    cards = [instant_card] * 30
    limit = 20  # Request 20, should cap at 15

    # Act
    result = format_card_list(cards, limit=limit)

    # Assert
    lines = result.split("\n")
    numbered_lines = [line for line in lines if line and line[0].isdigit()]
    assert len(numbered_lines) == 15  # Capped at 15
    assert "...and 15 more results" in result


def test_format_card_list_land_without_mana_cost(land_card: Card) -> None:
    """Test formatting list entry for land without mana cost."""
    # Arrange
    cards = [land_card]

    # Act
    result = format_card_list(cards)

    # Assert
    # Should show card name and type without mana cost
    assert "1. **Forest** - *Basic Land — Forest*" in result
    assert "{}" not in result  # No empty braces


def test_format_card_list_exactly_at_limit(instant_card: Card) -> None:
    """Test that list with exactly limit cards shows no truncation message."""
    # Arrange
    cards = [instant_card] * 10
    limit = 10

    # Act
    result = format_card_list(cards, limit=limit)

    # Assert
    lines = result.split("\n")
    numbered_lines = [line for line in lines if line and line[0].isdigit()]
    assert len(numbered_lines) == 10
    assert "...and" not in result  # No truncation message when exactly at limit


def test_format_card_list_truncation_singular(instant_card: Card) -> None:
    """Test truncation message uses singular form for 1 remaining card."""
    # Arrange
    cards = [instant_card] * 11
    limit = 10

    # Act
    result = format_card_list(cards, limit=limit)

    # Assert
    assert "...and 1 more result" in result  # Singular "result", not "results"
    # Verify it's not "1 more results" (plural form)
    assert "1 more results" not in result


def test_format_card_list_truncates_long_oracle_text() -> None:
    """Test that very long oracle text is truncated in list format."""
    # Arrange
    long_text = "This is a very long oracle text that goes on and on " * 10  # ~530 chars
    card = Card(
        id="test-long",
        name="Wordy Card",
        oracle_id="oracle-long",
        mana_cost="{2}{U}",
        cmc=3.0,
        type_line="Instant",
        oracle_text=long_text,
        rarity="rare",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "legal"},
    )

    # Act
    result = format_card_list([card])

    # Assert
    assert "**Wordy Card**" in result
    # Oracle text should be truncated to 150 chars with "..."
    assert "..." in result
    # Full oracle text should NOT be in result
    assert long_text not in result
    # Verify truncation happened (should be ~150 chars of oracle text shown)
    lines = result.split("\n")
    oracle_line = [line for line in lines if line.strip().startswith("This is a very long")][0]
    assert len(oracle_line.strip()) <= 153  # 150 chars + "..."


# Test format_card_with_image


def test_format_card_with_image_with_uris(instant_card: Card) -> None:
    """Test formatting card with image URIs returns text and image element."""
    # Arrange
    card_with_image = instant_card.model_copy(
        update={
            "image_uris": {
                "small": "https://cards.scryfall.io/small/front/test.jpg",
                "normal": "https://cards.scryfall.io/normal/front/test.jpg",
                "large": "https://cards.scryfall.io/large/front/test.jpg",
            }
        }
    )

    # Mock Chainlit module at the import point
    with patch("chainlit.Image") as mock_image_class:
        mock_image = MagicMock()
        mock_image.url = "https://cards.scryfall.io/normal/front/test.jpg"
        mock_image.name = "Lightning Bolt"
        mock_image.display = "inline"
        mock_image_class.return_value = mock_image

        # Act
        text, image = format_card_with_image(card_with_image)

        # Assert
        assert text is not None
        assert "**Lightning Bolt**" in text
        assert image is not None
        # Verify Image constructor was called with correct arguments
        mock_image_class.assert_called_once_with(
            url="https://cards.scryfall.io/normal/front/test.jpg",
            name="Lightning Bolt",
            display="inline",
        )


def test_format_card_with_image_without_uris(instant_card: Card) -> None:
    """Test formatting card without image URIs returns text only."""
    # Act
    text, image = format_card_with_image(instant_card)

    # Assert
    assert text is not None
    assert "**Lightning Bolt**" in text
    assert image is None


def test_format_card_with_image_missing_normal_size(instant_card: Card) -> None:
    """Test formatting card with incomplete image URIs returns text only."""
    # Arrange
    card_with_partial_images = instant_card.model_copy(
        update={
            "image_uris": {
                "small": "https://cards.scryfall.io/small/front/test.jpg",
                # Missing "normal" key
                "large": "https://cards.scryfall.io/large/front/test.jpg",
            }
        }
    )

    # Act
    text, image = format_card_with_image(card_with_partial_images)

    # Assert
    assert text is not None
    assert image is None  # No "normal" size, so no image element


def test_format_card_with_image_text_matches_format_card_details(instant_card: Card) -> None:
    """Test that text output from format_card_with_image matches format_card_details."""
    # Arrange
    card_with_image = instant_card.model_copy(
        update={
            "image_uris": {
                "normal": "https://cards.scryfall.io/normal/front/test.jpg",
            }
        }
    )

    # Mock Chainlit module
    with patch("chainlit.Image") as mock_image_class:
        mock_image_class.return_value = MagicMock()

        # Act
        text_from_image_formatter, _ = format_card_with_image(card_with_image)
        text_from_details_formatter = format_card_details(card_with_image)

        # Assert
        assert text_from_image_formatter == text_from_details_formatter


# Test dual-faced card helpers


def test_has_card_faces_single_faced_card(instant_card: Card) -> None:
    """Test that single-faced card is detected correctly."""
    # Act
    result = _has_card_faces(instant_card)

    # Assert
    assert result is False


def test_has_card_faces_dual_faced_card(transform_card: Card) -> None:
    """Test that dual-faced card is detected correctly."""
    # Act
    result = _has_card_faces(transform_card)

    # Assert
    assert result is True


def test_has_card_faces_empty_card_faces() -> None:
    """Test that card with empty card_faces array is treated as single-faced."""
    # Arrange
    card = Card(
        id="test-empty",
        name="Empty Card",
        oracle_id="oracle-empty",
        mana_cost="{1}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Test",
        rarity="common",
        set_code="TST",
        set_name="Test",
        collector_number="1",
        colors=[],
        color_identity=[],
        legalities={"standard": "legal"},
        card_faces=[],  # Empty array
    )

    # Act
    result = _has_card_faces(card)

    # Assert
    assert result is False


def test_format_card_face_front_face() -> None:
    """Test formatting of front face of dual-faced card."""
    # Arrange
    face = {
        "name": "Delver of Secrets",
        "mana_cost": "{U}",
        "type_line": "Creature — Human Wizard",
        "oracle_text": "At the beginning of your upkeep, look at the top card.",
    }

    # Act
    lines = _format_card_face(face, 0)
    result = "\n".join(lines)

    # Assert
    assert "**Front Face:**" in result
    assert "Delver of Secrets" in result
    assert "Mana Cost: {U}" in result
    assert "*Creature — Human Wizard*" in result
    assert "At the beginning of your upkeep" in result


def test_format_card_face_back_face() -> None:
    """Test formatting of back face of dual-faced card."""
    # Arrange
    face = {
        "name": "Insectile Aberration",
        "type_line": "Creature — Human Insect",
        "oracle_text": "Flying",
    }

    # Act
    lines = _format_card_face(face, 1)
    result = "\n".join(lines)

    # Assert
    assert "**Back Face:**" in result
    assert "Insectile Aberration" in result
    assert "*Creature — Human Insect*" in result
    assert "Flying" in result


# Test format_card_details with dual-faced cards


def test_format_card_details_transform_card(transform_card: Card) -> None:
    """Test formatting transform card with both faces."""
    # Act
    result = format_card_details(transform_card)

    # Assert
    assert "**Delver of Secrets // Insectile Aberration**" in result
    assert "**Front Face:**" in result
    assert "**Back Face:**" in result
    assert "Delver of Secrets" in result
    assert "Insectile Aberration" in result
    assert "At the beginning of your upkeep" in result
    assert "Flying" in result
    assert "Colors: U" in result
    assert "Innistrad" in result


def test_format_card_details_modal_dfc(modal_dfc_card: Card) -> None:
    """Test formatting modal DFC card (Sephiroth bug report example)."""
    # Act
    result = format_card_details(modal_dfc_card)

    # Assert
    assert "**Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel**" in result
    assert "**Front Face:**" in result
    assert "**Back Face:**" in result
    assert "Sephiroth, Fabled SOLDIER" in result
    assert "Sephiroth, One-Winged Angel" in result
    # Verify both oracle texts are present
    assert "Whenever Sephiroth, Fabled SOLDIER enters or attacks" in result
    assert "Flying, vigilance, lifelink" in result
    assert "Colors: B, W" in result


def test_format_card_details_backward_compatibility_single_face(instant_card: Card) -> None:
    """Test that single-faced cards still format correctly (backward compatibility)."""
    # Act
    result = format_card_details(instant_card)

    # Assert
    assert "**Lightning Bolt**" in result
    assert "Mana Cost: {R}" in result
    assert "*Instant*" in result
    assert "Lightning Bolt deals 3 damage" in result
    # Should NOT have face labels for single-faced cards
    assert "Front Face" not in result
    assert "Back Face" not in result


# Test format_card_list with dual-faced cards


def test_format_card_list_with_dual_faced_cards(instant_card: Card, transform_card: Card) -> None:
    """Test formatting list with mix of single and dual-faced cards."""
    # Arrange
    cards = [instant_card, transform_card]

    # Act
    result = format_card_list(cards)

    # Assert
    # Single-faced card
    assert "1. **Lightning Bolt** {R} - *Instant*" in result
    # Dual-faced card
    assert "2. **Delver of Secrets // Insectile Aberration** {U}" in result
    assert "Creature — Human Wizard // Creature — Human Insect" in result
    # Oracle text from both faces should be combined
    assert "At the beginning of your upkeep" in result or "Flying" in result


def test_format_card_list_dual_faced_oracle_text_truncation(modal_dfc_card: Card) -> None:
    """Test that dual-faced card oracle text is truncated correctly."""
    # Arrange
    cards = [modal_dfc_card]

    # Act
    result = format_card_list(cards)

    # Assert
    assert "**Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel**" in result
    # Long oracle text should be truncated
    assert "..." in result


def test_format_card_list_dual_faced_mana_cost_from_face(transform_card: Card) -> None:
    """Test that mana cost is extracted from first face when root is empty."""
    # Arrange
    cards = [transform_card]

    # Act
    result = format_card_list(cards)

    # Assert
    # Mana cost should be from first face
    assert "{U}" in result
    assert "**Delver of Secrets // Insectile Aberration** {U}" in result


# Test format_card_with_image with dual-faced cards


def test_format_card_with_image_dual_faced_with_image_in_faces(
    modal_dfc_card: Card,
) -> None:
    """Test formatting dual-faced card with image in card_faces."""
    # Mock Chainlit module
    with patch("chainlit.Image") as mock_image_class:
        mock_image = MagicMock()
        mock_image_class.return_value = mock_image

        # Act
        text, image = format_card_with_image(modal_dfc_card)

        # Assert
        assert text is not None
        assert "**Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel**" in text
        assert "**Front Face:**" in text
        assert "**Back Face:**" in text
        assert image is not None
        # Verify Image was called with front face image
        mock_image_class.assert_called_once_with(
            url="https://cards.scryfall.io/normal/front/sephiroth-front.jpg",
            name="Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel",
            display="inline",
        )


def test_format_card_with_image_dual_faced_no_images(transform_card: Card) -> None:
    """Test formatting dual-faced card without any images."""
    # Act
    text, image = format_card_with_image(transform_card)

    # Assert
    assert text is not None
    assert "**Delver of Secrets // Insectile Aberration**" in text
    assert image is None  # No images available


def test_format_card_with_image_dual_faced_missing_image_uris_in_face() -> None:
    """Test dual-faced card with card_faces but no image_uris in faces."""
    # Arrange
    card = Card(
        id="test-no-img",
        name="Test // Card",
        oracle_id="oracle-test",
        mana_cost="",
        cmc=1.0,
        type_line="Creature // Creature",
        oracle_text="",
        rarity="common",
        set_code="TST",
        set_name="Test",
        collector_number="1",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "legal"},
        card_faces=[
            {
                "name": "Test",
                "mana_cost": "{U}",
                "type_line": "Creature",
                "oracle_text": "Front",
                # No image_uris
            },
            {
                "name": "Card",
                "type_line": "Creature",
                "oracle_text": "Back",
                # No image_uris
            },
        ],
    )

    # Act
    text, image = format_card_with_image(card)

    # Assert
    assert text is not None
    assert image is None  # No images in faces


# Tests for wrap_card_name_with_hover


def test_wrap_card_name_with_hover_with_image():
    """Test wrapping card name with hover when image available."""
    # Arrange
    card = Card(
        id="test-123",
        name="Lightning Bolt",
        oracle_id="oracle-123",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "not_legal"},
        image_uris={"normal": "https://example.com/card.jpg"},
    )

    # Act
    result = wrap_card_name_with_hover("Lightning Bolt", card)

    # Assert
    assert '<span class="card-hover"' in result
    assert "style=\"--card-image-url: url('https://example.com/card.jpg')\"" in result
    assert "Lightning Bolt</span>" in result


def test_wrap_card_name_with_hover_no_image():
    """Test wrapping card name when no image available."""
    # Arrange
    card = Card(
        id="test-123",
        name="Lightning Bolt",
        oracle_id="oracle-123",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "not_legal"},
        image_uris=None,  # No images
    )

    # Act
    result = wrap_card_name_with_hover("Lightning Bolt", card)

    # Assert
    assert result == "Lightning Bolt"  # Plain text fallback
    assert "<span" not in result


def test_wrap_card_name_with_hover_no_card():
    """Test wrapping card name when card is None."""
    # Act
    result = wrap_card_name_with_hover("Lightning Bolt", None)

    # Assert
    assert result == "Lightning Bolt"  # Plain text fallback
    assert "<span" not in result


def test_wrap_card_name_with_hover_dual_faced_card():
    """Test wrapping card name for dual-faced card (uses front face image)."""
    # Arrange
    card = Card(
        id="test-dfc-123",
        name="Delver of Secrets // Insectile Aberration",
        oracle_id="oracle-dfc",
        mana_cost="{U}",
        cmc=1.0,
        type_line="Creature — Human Wizard // Creature — Human Insect",
        oracle_text="Transform card.",
        rarity="uncommon",
        set_code="ISD",
        set_name="Innistrad",
        collector_number="51",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "not_legal"},
        image_uris=None,  # Root-level has no images
        card_faces=[
            {
                "name": "Delver of Secrets",
                "image_uris": {"normal": "https://example.com/delver-front.jpg"},
            },
            {
                "name": "Insectile Aberration",
                "image_uris": {"normal": "https://example.com/delver-back.jpg"},
            },
        ],
    )

    # Act
    result = wrap_card_name_with_hover("Delver of Secrets // Insectile Aberration", card)

    # Assert
    assert '<span class="card-hover"' in result
    assert "url('https://example.com/delver-front.jpg')" in result  # Front face image


@patch("legacy.ui.formatters._use_card_image_hover")
def test_wrap_card_name_with_hover_feature_disabled(mock_use_hover):
    """Test wrapping card name when feature flag is disabled."""
    # Arrange
    mock_use_hover.return_value = False
    card = Card(
        id="test-123",
        name="Lightning Bolt",
        oracle_id="oracle-123",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "not_legal"},
        image_uris={"normal": "https://example.com/card.jpg"},
    )

    # Act
    result = wrap_card_name_with_hover("Lightning Bolt", card)

    # Assert
    assert result == "Lightning Bolt"  # Plain text when disabled
    assert "<span" not in result


def test_wrap_card_name_with_hover_html_escaping():
    """Test HTML escaping in card name and image URL."""
    # Arrange
    card = Card(
        id="test-123",
        name='Card with "quotes" & symbols',
        oracle_id="oracle-123",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "not_legal"},
        image_uris={"normal": "https://example.com/card?param=value&other=123"},
    )

    # Act
    result = wrap_card_name_with_hover('Card with "quotes" & symbols', card)

    # Assert
    assert "Card with &quot;quotes&quot; &amp; symbols" in result  # Name escaped
    assert "&amp;" in result  # URL param escaped
    assert "<script" not in result  # No injection

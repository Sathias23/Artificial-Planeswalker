"""Unit tests for JSON streaming parser."""

import json
from pathlib import Path

import pytest

from src.data.importers.parser import JSONParseError, stream_cards


@pytest.fixture
def sample_json_file():
    """Return path to sample Scryfall JSON fixture."""
    return Path(__file__).parent.parent.parent.parent / "fixtures" / "scryfall_sample.json"


def test_stream_cards_success(sample_json_file):
    """Test streaming valid JSON file yields card objects."""
    cards = list(stream_cards(sample_json_file))

    assert len(cards) == 6  # 5 valid + 1 invalid from fixture
    assert cards[0]["name"] == "Lightning Bolt"
    assert cards[1]["name"] == "Black Lotus"
    assert cards[2]["name"] == "Forest"
    assert cards[3]["name"] == "Delver of Secrets // Insectile Aberration"
    assert cards[4]["name"] == "Pact of Negation"


def test_stream_cards_iterates_correctly(sample_json_file):
    """Test that stream_cards yields cards one at a time."""
    card_generator = stream_cards(sample_json_file)

    # Get first card
    first_card = next(card_generator)
    assert first_card["name"] == "Lightning Bolt"

    # Get second card
    second_card = next(card_generator)
    assert second_card["name"] == "Black Lotus"


def test_stream_cards_file_not_found():
    """Test streaming non-existent file raises FileNotFoundError."""
    non_existent = Path("/tmp/does-not-exist.json")

    with pytest.raises(FileNotFoundError):
        list(stream_cards(non_existent))


def test_stream_cards_malformed_json(tmp_path):
    """Test streaming malformed JSON raises JSONParseError."""
    malformed_file = tmp_path / "malformed.json"
    malformed_file.write_text('{"incomplete": ')

    with pytest.raises(JSONParseError) as exc_info:
        list(stream_cards(malformed_file))

    assert "Malformed JSON" in str(exc_info.value)


def test_stream_cards_empty_array(tmp_path):
    """Test streaming empty JSON array works correctly."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("[]")

    cards = list(stream_cards(empty_file))
    assert len(cards) == 0


def test_stream_cards_single_card(tmp_path):
    """Test streaming single card JSON array."""
    single_card_file = tmp_path / "single.json"
    card_data = [
        {
            "id": "test-id",
            "name": "Test Card",
            "oracle_id": "test-oracle",
            "type_line": "Creature",
        }
    ]
    single_card_file.write_text(json.dumps(card_data))

    cards = list(stream_cards(single_card_file))
    assert len(cards) == 1
    assert cards[0]["name"] == "Test Card"

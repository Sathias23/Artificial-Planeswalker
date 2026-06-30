"""Streaming JSON parser for large Scryfall bulk data files."""

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import ijson

logger = logging.getLogger(__name__)


class JSONParseError(Exception):
    """Raised when JSON parsing fails."""

    pass


def stream_cards(file_path: Path) -> Iterator[dict[str, Any]]:
    """Stream card objects from Scryfall JSON file incrementally.

    Uses ijson to parse large JSON files without loading entirely into memory.
    Yields individual card objects from the top-level array.

    Args:
        file_path: Path to the Scryfall JSON file to parse.

    Yields:
        Dictionary representing a single card object.

    Raises:
        JSONParseError: If the JSON file is malformed or cannot be parsed.
        FileNotFoundError: If the file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {file_path}")

    logger.info(f"Starting streaming JSON parse: {file_path}")
    cards_count = 0

    try:
        with file_path.open("rb") as f:
            # Parse top-level array items incrementally
            # ijson.items(f, 'item') yields each element of the root array
            for card in ijson.items(f, "item"):
                cards_count += 1
                yield card

                # Log progress every 5,000 cards during parsing
                if cards_count % 5000 == 0:
                    logger.debug(f"Parsed {cards_count:,} cards")

        logger.info(f"Completed parsing {cards_count:,} cards from {file_path.name}")

    except ijson.JSONError as e:
        error_msg = f"Malformed JSON in {file_path.name}: {e}"
        logger.error(error_msg)
        raise JSONParseError(error_msg) from e

    except Exception as e:
        error_msg = f"Unexpected error parsing {file_path.name}: {e}"
        logger.error(error_msg)
        raise JSONParseError(error_msg) from e

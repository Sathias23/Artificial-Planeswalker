"""Main orchestrator for Scryfall bulk data import process."""

import logging
import tempfile
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.importers.importer import ImportStatistics, import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.scryfall_api import download_bulk_data, fetch_bulk_data_list
from src.data.importers.transformers import transform_scryfall_card
from src.data.models.card import CardModel

logger = logging.getLogger(__name__)


class ScryfallImportError(Exception):
    """Raised when Scryfall import process fails."""

    pass


async def import_scryfall_bulk_data(
    session: AsyncSession,
    bulk_type: str = "oracle_cards",
    temp_dir: Path | None = None,
) -> ImportStatistics:
    """Import Scryfall bulk data into database.

    Orchestrates the complete import process:
    1. Fetch bulk data metadata from Scryfall API
    2. Download the specified bulk data file
    3. Stream-parse the JSON file
    4. Transform card objects to CardModel instances
    5. Batch-insert cards into database

    Args:
        session: AsyncSession for database operations.
        bulk_type: Type of bulk data to import (default: "oracle_cards").
                   Options: "oracle_cards", "default_cards", "unique_artwork"
        temp_dir: Directory for temporary download files. Uses system temp if None.

    Returns:
        ImportStatistics with import metrics.

    Raises:
        ScryfallImportError: If any stage of the import fails.
    """
    logger.info(f"Starting Scryfall bulk data import (type: {bulk_type})")

    try:
        # Stage 1: Fetch bulk data metadata
        logger.info("Stage 1/5: Fetching bulk data metadata...")
        bulk_data_list = await fetch_bulk_data_list()

        # Find the requested bulk data type
        bulk_data = None
        for entry in bulk_data_list:
            if entry.get("type") == bulk_type:
                bulk_data = entry
                break

        if not bulk_data:
            available_types = [entry.get("type") for entry in bulk_data_list]
            raise ScryfallImportError(
                f"Bulk data type '{bulk_type}' not found. Available types: {available_types}"
            )

        download_uri = bulk_data["download_uri"]
        file_size_mb = bulk_data.get("size", 0) / (1024 * 1024)
        logger.info(f"Found bulk data: {bulk_type} ({file_size_mb:.1f} MB)")

        # Stage 2: Download bulk data file
        logger.info("Stage 2/5: Downloading bulk data file...")
        if temp_dir is None:
            temp_dir = Path(tempfile.gettempdir())

        output_file = temp_dir / f"scryfall_{bulk_type}.json"
        downloaded_file = await download_bulk_data(download_uri, output_file)

        # Stage 3: Stream-parse JSON file
        logger.info("Stage 3/5: Parsing JSON file...")
        cards_stream = stream_cards(downloaded_file)

        # Stage 4: Transform cards to CardModel instances
        logger.info("Stage 4/5: Transforming and importing cards...")

        # Create a generator that transforms each card
        def transform_cards() -> Iterator[CardModel | None]:
            for card_json in cards_stream:
                yield transform_scryfall_card(card_json)

        # Stage 5: Import cards into database
        logger.info("Stage 5/5: Batch importing into database...")
        stats = await import_cards(session, transform_cards())

        # Cleanup: Remove downloaded file
        try:
            downloaded_file.unlink()
            logger.info(f"Cleaned up temporary file: {downloaded_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file: {e}")

        logger.info("Import process completed successfully")
        return stats

    except Exception as e:
        error_msg = f"Scryfall import failed: {e}"
        logger.error(error_msg)
        raise ScryfallImportError(error_msg) from e

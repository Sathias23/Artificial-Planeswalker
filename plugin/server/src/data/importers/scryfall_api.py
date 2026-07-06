"""Scryfall API client for bulk data downloads."""

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SCRYFALL_BULK_DATA_URL = "https://api.scryfall.com/bulk-data"


class ScryfallAPIError(Exception):
    """Raised when Scryfall API requests fail."""

    pass


async def fetch_bulk_data_list(
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> list[dict[str, Any]]:
    """Fetch list of available Scryfall bulk data files.

    Args:
        max_retries: Maximum number of retry attempts on failure.
        retry_delay: Initial delay between retries in seconds (exponential backoff).

    Returns:
        List of bulk data objects with type, download_uri, size, updated_at fields.

    Raises:
        ScryfallAPIError: If all retry attempts fail.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching bulk data list (attempt {attempt + 1}/{max_retries})")
                response = await client.get(SCRYFALL_BULK_DATA_URL)
                response.raise_for_status()

                data = response.json()
                bulk_data_list: list[dict[str, Any]] = data.get("data", [])

                logger.info(f"Successfully fetched {len(bulk_data_list)} bulk data entries")
                return bulk_data_list

            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.warning(f"Bulk data list fetch failed: {e}")

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise ScryfallAPIError(
                        f"Failed to fetch bulk data list after {max_retries} attempts: {e}"
                    ) from e

    raise ScryfallAPIError("Unexpected error: Failed to fetch bulk data list")


async def download_bulk_data(
    download_uri: str,
    output_path: Path,
    chunk_size: int = 10 * 1024 * 1024,  # 10 MB chunks
    max_retries: int = 3,
    retry_delay: float = 2.0,
    max_bytes: int | None = None,
) -> Path:
    """Download Scryfall bulk data file with streaming and progress logging.

    Args:
        download_uri: URL to download bulk data from.
        output_path: Path to save downloaded file.
        chunk_size: Size of chunks to download (default 10 MB).
        max_retries: Maximum retry attempts on failure.
        retry_delay: Initial delay between retries (exponential backoff).
        max_bytes: Hard ceiling on downloaded bytes. A response that advertises or
            streams past it aborts immediately (no retry) — disk-exhaustion guard.

    Returns:
        Path to the downloaded file.

    Raises:
        ScryfallAPIError: If download fails after all retries, or exceeds *max_bytes*.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=300.0) as client:
        for attempt in range(max_retries):
            try:
                logger.info(f"Starting bulk data download (attempt {attempt + 1}/{max_retries})")
                logger.info(f"Download URI: {download_uri}")
                logger.info(f"Output path: {output_path}")

                async with client.stream("GET", download_uri) as response:
                    response.raise_for_status()

                    # Get file size if available
                    total_size = int(response.headers.get("content-length", 0))
                    total_mb = total_size / (1024 * 1024) if total_size else 0.0

                    if max_bytes is not None and total_size > max_bytes:
                        raise ScryfallAPIError(
                            f"Advertised download size ({total_size:,} bytes) exceeds the "
                            f"{max_bytes:,}-byte ceiling; aborting"
                        )

                    if total_size:
                        logger.info(f"File size: {total_mb:.1f} MB")

                    bytes_downloaded = 0
                    last_log_mb = 0.0

                    with output_path.open("wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size):
                            bytes_downloaded += len(chunk)
                            if max_bytes is not None and bytes_downloaded > max_bytes:
                                raise ScryfallAPIError(
                                    f"Download exceeded the {max_bytes:,}-byte ceiling "
                                    f"(content-length was absent or wrong); aborting"
                                )
                            f.write(chunk)

                            # Log progress every 10 MB
                            current_mb = bytes_downloaded / (1024 * 1024)
                            if current_mb - last_log_mb >= 10:
                                if total_size:
                                    percent = (bytes_downloaded / total_size) * 100
                                    logger.info(
                                        f"Downloaded {current_mb:.1f} MB / {total_mb:.1f} MB "
                                        f"({percent:.1f}%)"
                                    )
                                else:
                                    logger.info(f"Downloaded {current_mb:.1f} MB")
                                last_log_mb = current_mb

                final_mb = bytes_downloaded / (1024 * 1024)
                logger.info(f"Download complete: {final_mb:.1f} MB")
                return output_path

            except ScryfallAPIError:
                # Ceiling violations are deliberate aborts: drop the partial file and
                # propagate without retrying (the source would just oversend again).
                output_path.unlink(missing_ok=True)
                raise

            except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
                logger.warning(f"Download failed: {e}")

                # Remove partial file
                if output_path.exists():
                    output_path.unlink()

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise ScryfallAPIError(
                        f"Failed to download bulk data after {max_retries} attempts: {e}"
                    ) from e

    raise ScryfallAPIError("Unexpected error: Failed to download bulk data")

"""Commander Spellbook bulk-export downloader (Story 6.2, AD-9).

Sibling to :mod:`src.data.importers.scryfall_api`, mirroring its hardening: streaming
download, hard byte ceiling with no-retry abort + partial-file cleanup, and manual
exponential backoff (``tenacity`` is deliberately NOT a dependency). Differences are
deliberate: the URL is a pinned constant (no metadata indirection, so no download-URI
validation counterpart is needed) and the client sends an explicit descriptive
``User-Agent`` AND ``Accept`` header (the AD-9 rule postdates the Scryfall client).

The httpx decoding trap (verified live 2026-07-16): the ``.gz`` object is served with
``Content-Encoding: gzip`` and httpx auto-decompresses encoded responses. Streaming via
``response.aiter_bytes()`` would yield the ~579 MB DECODED stream — silently blowing
the ceiling and writing plain JSON that ``gzip.open`` rejects. This module streams
``response.aiter_raw()`` so the compressed wire bytes (~26 MB) land on disk and the
ceiling measures what ``content-length`` advertises.
"""

import asyncio
import logging
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

#: The pinned Commander Spellbook bulk variant export (regenerated upstream ~2-hourly).
SPELLBOOK_VARIANTS_URL = "https://json.commanderspellbook.com/variants.json.gz"

#: Hard default ceiling on downloaded (compressed wire) bytes. The gzip export is
#: ~26 MB today — generous headroom for growth while staying disk-safe.
DEFAULT_MAX_BYTES = 256 * 1024**2


def _user_agent() -> str:
    """Build the descriptive User-Agent with package version and repo contact URL."""
    try:
        pkg_version = version("artificial-planeswalker")
    except PackageNotFoundError:  # pragma: no cover - editable installs always resolve
        pkg_version = "unknown"
    return (
        f"Artificial-Planeswalker/{pkg_version} "
        "(+https://github.com/Sathias23/Artificial-Planeswalker)"
    )


class SpellbookAPIError(Exception):
    """Raised when the Spellbook bulk-export download fails."""


async def download_variants_export(
    output_path: Path,
    *,
    chunk_size: int = 10 * 1024 * 1024,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Path:
    """Download the Spellbook bulk variant export with streaming and hardening.

    Args:
        output_path: Path to save the downloaded ``.gz`` file (parent dirs created).
        chunk_size: Size of streamed chunks (default 10 MB).
        max_retries: Maximum retry attempts on transport failure.
        retry_delay: Initial delay between retries in seconds (exponential backoff:
            ``retry_delay * 2**attempt``).
        max_bytes: Hard ceiling on downloaded wire bytes. A response that advertises
            or streams past it aborts immediately (partial file deleted, NO retry).

    Returns:
        Path to the downloaded file.

    Raises:
        SpellbookAPIError: If the download fails after all retries, or exceeds
            *max_bytes*.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": _user_agent(), "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=300.0, headers=headers) as client:
        for attempt in range(max_retries):
            try:
                logger.info(
                    "Downloading Spellbook variants export (attempt %d/%d) from %s",
                    attempt + 1,
                    max_retries,
                    SPELLBOOK_VARIANTS_URL,
                )

                async with client.stream("GET", SPELLBOOK_VARIANTS_URL) as response:
                    response.raise_for_status()

                    total_size = int(response.headers.get("content-length", 0))
                    if total_size > max_bytes:
                        raise SpellbookAPIError(
                            f"Advertised download size ({total_size:,} bytes) exceeds "
                            f"the {max_bytes:,}-byte ceiling; aborting"
                        )
                    if total_size:
                        logger.info("File size: %.1f MB", total_size / (1024 * 1024))

                    bytes_downloaded = 0
                    last_log_mb = 0.0

                    with output_path.open("wb") as f:
                        # aiter_raw, NOT aiter_bytes: keep the compressed wire bytes
                        # (httpx would otherwise auto-decompress the gzip encoding).
                        async for chunk in response.aiter_raw(chunk_size):
                            bytes_downloaded += len(chunk)
                            if bytes_downloaded > max_bytes:
                                raise SpellbookAPIError(
                                    f"Download exceeded the {max_bytes:,}-byte ceiling "
                                    f"(content-length was absent or wrong); aborting"
                                )
                            f.write(chunk)

                            current_mb = bytes_downloaded / (1024 * 1024)
                            if current_mb - last_log_mb >= 10:
                                logger.info("Downloaded %.1f MB", current_mb)
                                last_log_mb = current_mb

                logger.info("Download complete: %.1f MB", bytes_downloaded / (1024 * 1024))
                return output_path

            except SpellbookAPIError:
                # Ceiling violations are deliberate aborts: drop the partial file and
                # propagate without retrying (the source would just oversend again).
                output_path.unlink(missing_ok=True)
                raise

            except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
                logger.warning("Download failed: %s", e)
                output_path.unlink(missing_ok=True)

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.info("Retrying in %.1f seconds...", delay)
                    await asyncio.sleep(delay)
                else:
                    raise SpellbookAPIError(
                        f"Failed to download variants export after {max_retries} attempts: {e}"
                    ) from e

    raise SpellbookAPIError("Unexpected error: failed to download variants export")

"""Scryfall symbology integration for visual mana symbol rendering.

This module provides caching and lookup utilities for Scryfall's Card Symbols API,
enabling visual rendering of mana costs and symbols using SVG images from Scryfall's CDN.

The symbol cache is populated lazily on first use and persists for the application lifetime.
If the Scryfall API is unavailable, symbols gracefully fall back to text notation.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# API Configuration
SCRYFALL_SYMBOLOGY_URL = "https://api.scryfall.com/symbology"
API_TIMEOUT_SECONDS = 5


class SymbologyAPIError(Exception):
    """Raised when Scryfall symbology API request fails."""

    pass


@dataclass
class SymbolMetadata:
    """Metadata for a Magic: The Gathering mana symbol from Scryfall."""

    symbol: str
    svg_uri: str
    colors: list[str]
    english: str
    mana_value: float


# Module-level cache for symbol metadata
_symbol_cache: dict[str, SymbolMetadata] | None = None


async def fetch_scryfall_symbols() -> dict[str, SymbolMetadata]:
    """Fetch all card symbols from Scryfall's symbology API.

    Makes a single GET request to Scryfall's /symbology endpoint and parses
    the response into SymbolMetadata objects.

    Returns:
        dict[str, SymbolMetadata]: Symbol metadata indexed by symbol string (e.g., "{R}")

    Raises:
        SymbologyAPIError: If the API request fails or returns invalid data
    """
    logger.info("Fetching card symbols from Scryfall API...")

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
            response = await client.get(SCRYFALL_SYMBOLOGY_URL)
            response.raise_for_status()

            data = response.json()
            symbols_data = data.get("data", [])

            if not symbols_data:
                raise SymbologyAPIError("Scryfall API returned no symbol data")

            # Parse symbols into cache
            symbol_cache: dict[str, SymbolMetadata] = {}
            for symbol_obj in symbols_data:
                try:
                    metadata = SymbolMetadata(
                        symbol=symbol_obj["symbol"],
                        svg_uri=symbol_obj["svg_uri"],
                        colors=symbol_obj.get("colors", []),
                        english=symbol_obj.get("english", ""),
                        mana_value=symbol_obj.get("mana_value", 0.0),
                    )
                    symbol_cache[metadata.symbol] = metadata
                except (KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse symbol object: {symbol_obj} - {e}")
                    continue

            logger.info(f"Successfully cached {len(symbol_cache)} symbols from Scryfall")
            return symbol_cache

    except httpx.TimeoutException as e:
        msg = f"Scryfall API request timed out after {API_TIMEOUT_SECONDS}s"
        raise SymbologyAPIError(msg) from e
    except httpx.HTTPStatusError as e:
        raise SymbologyAPIError(f"Scryfall API returned error: {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise SymbologyAPIError(f"Failed to connect to Scryfall API: {e}") from e
    except (KeyError, ValueError) as e:
        raise SymbologyAPIError(f"Failed to parse Scryfall API response: {e}") from e


async def get_symbol_cache() -> dict[str, SymbolMetadata]:
    """Get the symbol cache, initializing it lazily on first call.

    The cache is populated once per application lifetime. If initialization fails,
    an empty dict is returned and symbols will fall back to text notation.

    Returns:
        dict[str, SymbolMetadata]: Symbol metadata indexed by symbol string
    """
    global _symbol_cache

    if _symbol_cache is not None:
        return _symbol_cache

    try:
        _symbol_cache = await fetch_scryfall_symbols()
        return _symbol_cache
    except SymbologyAPIError as e:
        logger.warning(f"Failed to initialize symbol cache: {e}")
        logger.warning("Falling back to text notation for mana symbols")
        _symbol_cache = {}
        return _symbol_cache


async def get_symbol_svg_url(symbol: str) -> str | None:
    """Look up the SVG URL for a mana symbol (async version).

    Args:
        symbol: The symbol notation (e.g., "{R}", "{2}", "{W/U}")

    Returns:
        str | None: The Scryfall CDN URL for the symbol's SVG, or None if not found
    """
    cache = await get_symbol_cache()

    if symbol in cache:
        return cache[symbol].svg_uri

    # Log at debug level - missing symbols are expected for some edge cases
    logger.debug(f"Symbol not found in cache: {symbol}")
    return None


def get_symbol_svg_url_sync(symbol: str) -> str | None:
    """Look up the SVG URL for a mana symbol (sync version).

    This function only works if the cache has already been initialized.
    If the cache is not initialized, returns None (triggering text fallback).

    Use this from synchronous contexts. For async contexts, prefer get_symbol_svg_url().

    Args:
        symbol: The symbol notation (e.g., "{R}", "{2}", "{W/U}")

    Returns:
        str | None: The Scryfall CDN URL for the symbol's SVG, or None if not found
                   or cache not initialized
    """
    global _symbol_cache

    # If cache not initialized, return None (triggers text fallback)
    if _symbol_cache is None:
        return None

    if symbol in _symbol_cache:
        return _symbol_cache[symbol].svg_uri

    # Log at debug level - missing symbols are expected for some edge cases
    logger.debug(f"Symbol not found in cache: {symbol}")
    return None

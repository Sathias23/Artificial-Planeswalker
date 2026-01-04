"""Unit tests for src/ui/symbols.py - Scryfall symbology integration."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ui.symbols import (
    SymbolMetadata,
    SymbologyAPIError,
    fetch_scryfall_symbols,
    get_symbol_cache,
    get_symbol_svg_url,
    get_symbol_svg_url_sync,
)


class TestSymbolMetadata:
    """Tests for SymbolMetadata dataclass."""

    def test_symbol_metadata_creation(self):
        """Test creating SymbolMetadata with all fields."""
        metadata = SymbolMetadata(
            symbol="{R}",
            svg_uri="https://svgs.scryfall.io/card-symbols/R.svg",
            colors=["R"],
            english="one red mana",
            mana_value=1.0,
        )

        assert metadata.symbol == "{R}"
        assert metadata.svg_uri == "https://svgs.scryfall.io/card-symbols/R.svg"
        assert metadata.colors == ["R"]
        assert metadata.english == "one red mana"
        assert metadata.mana_value == 1.0


class TestFetchScryfallSymbols:
    """Tests for fetch_scryfall_symbols() function."""

    @pytest.mark.asyncio
    async def test_fetch_symbols_success(self):
        """Test successful fetch of symbols from Scryfall API."""
        mock_response_data = {
            "data": [
                {
                    "symbol": "{R}",
                    "svg_uri": "https://svgs.scryfall.io/card-symbols/R.svg",
                    "colors": ["R"],
                    "english": "one red mana",
                    "mana_value": 1.0,
                },
                {
                    "symbol": "{G}",
                    "svg_uri": "https://svgs.scryfall.io/card-symbols/G.svg",
                    "colors": ["G"],
                    "english": "one green mana",
                    "mana_value": 1.0,
                },
            ]
        }

        # Create mock response with synchronous json() method (httpx behavior)
        mock_response = AsyncMock()
        mock_response.json = Mock(return_value=mock_response_data)  # Synchronous, not async
        mock_response.raise_for_status = AsyncMock()

        # Create mock client that returns the response
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance

        with patch("src.ui.symbols.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_scryfall_symbols()

        assert len(result) == 2
        assert "{R}" in result
        assert "{G}" in result
        assert result["{R}"].svg_uri == "https://svgs.scryfall.io/card-symbols/R.svg"
        assert result["{G}"].colors == ["G"]

    @pytest.mark.asyncio
    async def test_fetch_symbols_empty_data(self):
        """Test handling of empty data response from API."""
        mock_response_data = {"data": []}

        mock_response = AsyncMock()
        mock_response.json = Mock(return_value=mock_response_data)  # Synchronous
        mock_response.raise_for_status = AsyncMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance

        with patch("src.ui.symbols.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(SymbologyAPIError, match="no symbol data"):
                await fetch_scryfall_symbols()

    @pytest.mark.asyncio
    async def test_fetch_symbols_timeout(self):
        """Test handling of API timeout."""
        import httpx

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance

        with patch("src.ui.symbols.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(SymbologyAPIError, match="timed out"):
                await fetch_scryfall_symbols()

    @pytest.mark.asyncio
    async def test_fetch_symbols_http_error(self):
        """Test handling of HTTP error response."""
        import httpx

        mock_response = AsyncMock()
        mock_response.status_code = 500

        def raise_http_error():
            raise httpx.HTTPStatusError("Server error", request=AsyncMock(), response=mock_response)

        mock_response.raise_for_status = raise_http_error

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance

        with patch("src.ui.symbols.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(SymbologyAPIError, match="returned error"):
                await fetch_scryfall_symbols()

    @pytest.mark.asyncio
    async def test_fetch_symbols_malformed_data(self):
        """Test handling of malformed symbol data (missing required fields)."""
        mock_response_data = {
            "data": [
                {
                    "symbol": "{R}",
                    "svg_uri": "https://svgs.scryfall.io/card-symbols/R.svg",
                    "colors": ["R"],
                    "english": "one red mana",
                    "mana_value": 1.0,
                },
                {
                    # Missing 'symbol' field - should be skipped with warning
                    "svg_uri": "https://svgs.scryfall.io/card-symbols/G.svg",
                    "colors": ["G"],
                },
            ]
        }

        mock_response = AsyncMock()
        mock_response.json = Mock(return_value=mock_response_data)  # Synchronous
        mock_response.raise_for_status = AsyncMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance

        with patch("src.ui.symbols.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_scryfall_symbols()

        # Only valid symbol should be in cache
        assert len(result) == 1
        assert "{R}" in result


class TestGetSymbolCache:
    """Tests for get_symbol_cache() function."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self):
        """Test that cache is initialized on first call."""
        # Reset cache
        import src.ui.symbols as symbols_module

        symbols_module._symbol_cache = None

        mock_response_data = {
            "data": [
                {
                    "symbol": "{R}",
                    "svg_uri": "https://svgs.scryfall.io/card-symbols/R.svg",
                    "colors": ["R"],
                    "english": "one red mana",
                    "mana_value": 1.0,
                }
            ]
        }

        mock_response = AsyncMock()
        mock_response.json = Mock(return_value=mock_response_data)  # Synchronous
        mock_response.raise_for_status = AsyncMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance

        with patch("src.ui.symbols.httpx.AsyncClient", return_value=mock_client):
            cache = await get_symbol_cache()

        assert len(cache) == 1
        assert "{R}" in cache

    @pytest.mark.asyncio
    async def test_cache_reuse(self):
        """Test that cache is reused on subsequent calls."""
        # Pre-populate cache
        import src.ui.symbols as symbols_module

        test_cache = {
            "{R}": SymbolMetadata(
                symbol="{R}",
                svg_uri="https://test.com/R.svg",
                colors=["R"],
                english="red",
                mana_value=1.0,
            )
        }
        symbols_module._symbol_cache = test_cache

        # Should return cached value without making API call
        cache = await get_symbol_cache()

        assert cache is test_cache
        assert "{R}" in cache

    @pytest.mark.asyncio
    async def test_cache_initialization_failure(self):
        """Test graceful handling of cache initialization failure."""
        # Reset cache
        import src.ui.symbols as symbols_module

        symbols_module._symbol_cache = None

        # Mock API failure
        import httpx

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client_instance

        with patch("src.ui.symbols.httpx.AsyncClient", return_value=mock_client):
            cache = await get_symbol_cache()

        # Should return empty dict on failure
        assert cache == {}
        assert symbols_module._symbol_cache == {}


class TestGetSymbolSvgUrl:
    """Tests for get_symbol_svg_url() async function."""

    @pytest.mark.asyncio
    async def test_get_symbol_found(self):
        """Test getting SVG URL for a symbol in cache."""
        # Pre-populate cache
        import src.ui.symbols as symbols_module

        test_cache = {
            "{R}": SymbolMetadata(
                symbol="{R}",
                svg_uri="https://svgs.scryfall.io/card-symbols/R.svg",
                colors=["R"],
                english="red",
                mana_value=1.0,
            )
        }
        symbols_module._symbol_cache = test_cache

        url = await get_symbol_svg_url("{R}")

        assert url == "https://svgs.scryfall.io/card-symbols/R.svg"

    @pytest.mark.asyncio
    async def test_get_symbol_not_found(self):
        """Test getting SVG URL for unknown symbol."""
        # Pre-populate cache
        import src.ui.symbols as symbols_module

        test_cache = {
            "{R}": SymbolMetadata(
                symbol="{R}",
                svg_uri="https://svgs.scryfall.io/card-symbols/R.svg",
                colors=["R"],
                english="red",
                mana_value=1.0,
            )
        }
        symbols_module._symbol_cache = test_cache

        url = await get_symbol_svg_url("{UNKNOWN}")

        assert url is None


class TestGetSymbolSvgUrlSync:
    """Tests for get_symbol_svg_url_sync() synchronous function."""

    def test_get_symbol_sync_found(self):
        """Test sync lookup for symbol in cache."""
        # Pre-populate cache
        import src.ui.symbols as symbols_module

        test_cache = {
            "{G}": SymbolMetadata(
                symbol="{G}",
                svg_uri="https://svgs.scryfall.io/card-symbols/G.svg",
                colors=["G"],
                english="green",
                mana_value=1.0,
            )
        }
        symbols_module._symbol_cache = test_cache

        url = get_symbol_svg_url_sync("{G}")

        assert url == "https://svgs.scryfall.io/card-symbols/G.svg"

    def test_get_symbol_sync_not_found(self):
        """Test sync lookup for unknown symbol."""
        # Pre-populate cache
        import src.ui.symbols as symbols_module

        test_cache = {
            "{G}": SymbolMetadata(
                symbol="{G}",
                svg_uri="https://svgs.scryfall.io/card-symbols/G.svg",
                colors=["G"],
                english="green",
                mana_value=1.0,
            )
        }
        symbols_module._symbol_cache = test_cache

        url = get_symbol_svg_url_sync("{UNKNOWN}")

        assert url is None

    def test_get_symbol_sync_cache_not_initialized(self):
        """Test sync lookup when cache is not initialized."""
        # Reset cache to uninitialized state
        import src.ui.symbols as symbols_module

        symbols_module._symbol_cache = None

        url = get_symbol_svg_url_sync("{R}")

        # Should return None when cache not initialized
        assert url is None

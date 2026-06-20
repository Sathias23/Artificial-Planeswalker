"""Unit tests for visual symbol rendering in src/ui/formatters.py."""

from unittest.mock import patch

from legacy.ui.formatters import (
    _use_visual_symbols,
    format_mana_symbols,
    parse_mana_cost,
    render_oracle_text_symbols,
    render_symbol_as_html,
)


class TestUseVisualSymbols:
    """Tests for _use_visual_symbols() configuration helper."""

    def test_default_true(self):
        """Test that visual symbols are enabled by default."""
        with patch.dict("os.environ", {}, clear=True):
            # No env var set - should default to True
            assert _use_visual_symbols() is True

    def test_explicit_true(self):
        """Test explicit true values."""
        for value in ["true", "True", "TRUE", "1", "yes", "YES"]:
            with patch.dict("os.environ", {"VISUAL_MANA_SYMBOLS": value}):
                assert _use_visual_symbols() is True

    def test_explicit_false(self):
        """Test explicit false values."""
        for value in ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"]:
            with patch.dict("os.environ", {"VISUAL_MANA_SYMBOLS": value}):
                assert _use_visual_symbols() is False

    def test_invalid_value_defaults_true(self):
        """Test that invalid values default to True."""
        with patch.dict("os.environ", {"VISUAL_MANA_SYMBOLS": "invalid"}):
            assert _use_visual_symbols() is True


class TestParseManaCost:
    """Tests for parse_mana_cost() function."""

    def test_parse_simple_mana_cost(self):
        """Test parsing simple mana cost."""
        result = parse_mana_cost("{2}{R}{G}")
        assert result == ["{2}", "{R}", "{G}"]

    def test_parse_hybrid_mana(self):
        """Test parsing hybrid mana symbols."""
        result = parse_mana_cost("{W/U}{2/R}")
        assert result == ["{W/U}", "{2/R}"]

    def test_parse_phyrexian_mana(self):
        """Test parsing Phyrexian mana symbols."""
        result = parse_mana_cost("{W/P}{U/P}")
        assert result == ["{W/P}", "{U/P}"]

    def test_parse_colorless_mana(self):
        """Test parsing colorless mana."""
        result = parse_mana_cost("{C}{C}")
        assert result == ["{C}", "{C}"]

    def test_parse_x_costs(self):
        """Test parsing X, Y, Z costs."""
        result = parse_mana_cost("{X}{Y}{Z}")
        assert result == ["{X}", "{Y}", "{Z}"]

    def test_parse_empty_string(self):
        """Test parsing empty mana cost."""
        result = parse_mana_cost("")
        assert result == []

    def test_parse_none(self):
        """Test parsing None mana cost."""
        result = parse_mana_cost(None)
        assert result == []

    def test_parse_complex_cost(self):
        """Test parsing complex mana cost with multiple symbol types."""
        result = parse_mana_cost("{4}{W/U}{B/P}{C}")
        assert result == ["{4}", "{W/U}", "{B/P}", "{C}"]


class TestRenderSymbolAsHtml:
    """Tests for render_symbol_as_html() function."""

    def test_render_symbol_found_in_cache(self):
        """Test rendering symbol that exists in cache."""
        # Mock the symbol cache
        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            mock_get_url.return_value = "https://svgs.scryfall.io/card-symbols/R.svg"

            result = render_symbol_as_html("{R}")

            assert '<img src="https://svgs.scryfall.io/card-symbols/R.svg"' in result
            assert 'alt="{R}"' in result
            assert 'class="mana-symbol"' in result

    def test_render_symbol_not_found(self):
        """Test rendering symbol not in cache (falls back to text)."""
        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            mock_get_url.return_value = None

            result = render_symbol_as_html("{UNKNOWN}")

            # Should return HTML-escaped text
            assert result == "{UNKNOWN}"
            assert "<img" not in result

    def test_render_symbol_escapes_html(self):
        """Test that symbol text is HTML-escaped in alt attribute."""
        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            mock_get_url.return_value = "https://svgs.scryfall.io/card-symbols/R.svg"

            result = render_symbol_as_html("{R}")

            # Alt text should be properly escaped
            assert 'alt="{R}"' in result


class TestFormatManaSymbols:
    """Tests for format_mana_symbols() function."""

    def test_format_empty_mana_cost(self):
        """Test formatting empty mana cost."""
        result = format_mana_symbols("")
        assert result == ""

    def test_format_with_visual_true(self):
        """Test formatting with visual symbols enabled."""
        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            mock_get_url.return_value = "https://svgs.scryfall.io/card-symbols/R.svg"

            result = format_mana_symbols("{R}{G}", use_visual=True)

            assert "<img" in result
            assert 'class="mana-symbol"' in result
            # Should have 2 img tags
            assert result.count("<img") == 2

    def test_format_with_visual_false(self):
        """Test formatting with visual symbols disabled."""
        result = format_mana_symbols("{2}{R}{G}", use_visual=False)

        # Should return text as-is
        assert result == "{2}{R}{G}"
        assert "<img" not in result

    def test_format_uses_env_var_by_default(self):
        """Test that format uses environment variable when use_visual=None."""
        with patch("legacy.ui.formatters._use_visual_symbols") as mock_use_visual:
            mock_use_visual.return_value = False

            result = format_mana_symbols("{R}", use_visual=None)

            # Should use env var setting (False)
            assert result == "{R}"
            mock_use_visual.assert_called_once()

    def test_format_hybrid_mana(self):
        """Test formatting hybrid mana cost."""
        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            mock_get_url.return_value = "https://svgs.scryfall.io/card-symbols/WU.svg"

            result = format_mana_symbols("{W/U}", use_visual=True)

            assert "<img" in result
            assert 'alt="{W/U}"' in result

    def test_format_fallback_on_error(self):
        """Test fallback to text on rendering error."""
        with patch("legacy.ui.formatters.parse_mana_cost") as mock_parse:
            # Simulate error in parsing
            mock_parse.side_effect = Exception("Test error")

            result = format_mana_symbols("{R}{G}", use_visual=True)

            # Should fall back to escaped text
            assert result == "{R}{G}"

    def test_format_mixed_found_and_not_found_symbols(self):
        """Test formatting with some symbols in cache, some not."""

        def mock_get_url(symbol):
            if symbol == "{R}":
                return "https://svgs.scryfall.io/card-symbols/R.svg"
            return None  # {UNKNOWN} not found

        with patch("legacy.ui.symbols.get_symbol_svg_url_sync", side_effect=mock_get_url):
            result = format_mana_symbols("{R}{UNKNOWN}", use_visual=True)

            # {R} should be image, {UNKNOWN} should be text
            assert "<img" in result
            assert "{UNKNOWN}" in result


class TestRenderOracleTextSymbols:
    """Tests for render_oracle_text_symbols() function."""

    def test_render_oracle_text_with_symbols(self):
        """Test rendering oracle text with inline symbols."""
        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            mock_get_url.side_effect = lambda s: (
                "https://svgs.scryfall.io/card-symbols/T.svg"
                if s == "{T}"
                else "https://svgs.scryfall.io/card-symbols/R.svg"
            )

            result = render_oracle_text_symbols("{T}: Add {R}", use_visual=True)

            assert "<img" in result
            assert "Add" in result  # Text should be preserved
            # Should have 2 img tags
            assert result.count("<img") == 2

    def test_render_oracle_text_no_symbols(self):
        """Test rendering oracle text without symbols."""
        result = render_oracle_text_symbols("Draw a card.", use_visual=True)

        # Should return text as-is (HTML-escaped)
        assert result == "Draw a card."
        assert "<img" not in result

    def test_render_oracle_text_visual_false(self):
        """Test rendering with visual disabled."""
        result = render_oracle_text_symbols("{T}: Add {R}", use_visual=False)

        # Should return original text
        assert result == "{T}: Add {R}"
        assert "<img" not in result

    def test_render_oracle_text_empty(self):
        """Test rendering empty oracle text."""
        result = render_oracle_text_symbols("", use_visual=True)
        assert result == ""

    def test_render_oracle_text_html_escaping(self):
        """Test that non-symbol text is HTML-escaped."""
        result = render_oracle_text_symbols("<script>alert('xss')</script>", use_visual=True)

        # Should escape HTML special characters
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_render_oracle_text_preserves_structure(self):
        """Test that text structure is preserved."""
        oracle_text = "First ability.\nSecond ability with {T}."

        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            mock_get_url.return_value = "https://svgs.scryfall.io/card-symbols/T.svg"

            result = render_oracle_text_symbols(oracle_text, use_visual=True)

            # Newlines should be preserved
            assert "\n" in result
            assert "First ability." in result
            assert "Second ability with" in result

    def test_render_oracle_text_uses_env_var_by_default(self):
        """Test that render uses environment variable when use_visual=None."""
        with patch("legacy.ui.formatters._use_visual_symbols") as mock_use_visual:
            mock_use_visual.return_value = False

            result = render_oracle_text_symbols("{T}: Tap", use_visual=None)

            # Should use env var setting (False)
            assert result == "{T}: Tap"
            mock_use_visual.assert_called_once()

    def test_render_oracle_text_fallback_on_error(self):
        """Test fallback to text on rendering error."""
        with patch("legacy.ui.formatters.re.split") as mock_split:
            # Simulate error in regex split
            mock_split.side_effect = Exception("Test error")

            result = render_oracle_text_symbols("{T}: Add {R}", use_visual=True)

            # Should fall back to escaped text
            assert result == "{T}: Add {R}"
            assert "<img" not in result

    def test_render_complex_oracle_text(self):
        """Test rendering complex oracle text with multiple symbols."""
        oracle_text = "{2}{R}{R}, {T}: This deals 3 damage. Add {R}{R}{R}."

        with patch("legacy.ui.symbols.get_symbol_svg_url_sync") as mock_get_url:
            # All symbols found
            mock_get_url.return_value = "https://svgs.scryfall.io/card-symbols/test.svg"

            result = render_oracle_text_symbols(oracle_text, use_visual=True)

            # Should have 7 img tags (2, R, R, T, R, R, R)
            assert result.count("<img") == 7
            assert "deals 3 damage" in result  # Text preserved
            assert "Add" in result

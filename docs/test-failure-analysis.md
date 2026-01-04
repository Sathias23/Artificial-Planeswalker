# Test Failure Analysis

**Date:** 2025-10-20
**Total Failures:** 19 failures, 426 passed, 1 skipped

## Summary by Category

### 1. Visual Mana Symbols Feature - Tests Need Updating (13 failures)

**Status:** ✅ **Not a Bug** - Tests written before visual symbols feature
**Action Required:** Update test assertions to check for SVG HTML instead of text notation

**Root Cause:**
The visual mana symbols feature (using Scryfall SVG API) was added recently. Tests were written expecting text notation like `{R}`, `{1}{G}`, but the code now correctly returns SVG HTML like `<img src="https://svgs.scryfall.io/card-symbols/R.svg" alt="{R}" class="mana-symbol" />`.

**Affected Tests:**
- `tests/unit/ui/test_formatters.py`:
  - `test_format_mana_symbols_basic_colors`
  - `test_format_mana_symbols_complex`
  - `test_format_card_details_creature`
  - `test_format_card_details_instant_with_text`
  - `test_format_card_details_land_no_mana_cost`
  - `test_format_card_list_single_card`
  - `test_format_card_list_multiple_cards_under_limit`
  - `test_format_card_face_front_face`
  - `test_format_card_details_backward_compatibility_single_face`
  - `test_format_card_list_with_dual_faced_cards`
  - `test_format_card_list_dual_faced_mana_cost_from_face`
- `tests/unit/agent/tools/test_card_lookup.py`:
  - `test_exact_match_found`
  - `test_handles_colorless_card`

**Fix Strategy:**
```python
# Old assertion (fails):
assert "Mana Cost: {R}" in result

# New assertion (correct):
assert 'Mana Cost: <img src="https://svgs.scryfall.io/card-symbols/R.svg" alt="{R}" class="mana-symbol" />' in result
# OR check for alt text:
assert 'alt="{R}"' in result
```

**Recommendation:**
Batch update all assertions to check for `<img src=` and `alt="{X}"` patterns. Consider adding a test environment variable `VISUAL_MANA_SYMBOLS=false` to run tests in text-only mode if needed.

---

### 2. Logfire Configuration Tests - Environment Isolation (3 failures)

**Status:** ⚠️ **Test Isolation Issue**
**Action Required:** Mock environment variables in tests

**Root Cause:**
Tests are using the user's actual `.env` file which has `LOGFIRE_ENABLED=true` and a real `LOGFIRE_TOKEN` set. Tests expect default values but environment variables override the defaults.

**Affected Tests:**
- `tests/unit/agent/test_logfire_config.py`:
  - `test_logfire_disabled_by_default` - Expects `logfire_enabled=False`, but `.env` has `true`
  - `test_logfire_enabled_without_token_raises_error` - Expects ValidationError, but `.env` has valid token
  - `test_logfire_disabled_without_token_loads_successfully` - Expects `logfire_token=None`, but `.env` has token

**Evidence:**
```python
# Test expects: logfire_enabled=False
# Actual from .env: logfire_enabled=True
assert config.logfire_enabled is False  # ❌ Fails
```

**Fix Strategy:**
```python
import pytest
from unittest.mock import patch

def test_logfire_disabled_by_default():
    # Mock environment to remove overrides
    with patch.dict('os.environ', {}, clear=True):
        config = AgentConfig(openrouter_api_key="test-key")
        assert config.logfire_enabled is False
```

**Recommendation:**
All config tests should use `pytest-env` or `unittest.mock.patch` to isolate environment variables. Create a test fixture that clears environment before each test.

---

### 3. Deck Format Validation - Potential Bug (1 failure)

**Status:** 🐛 **Possible Bug**
**Action Required:** Investigate format validation in Pydantic schema

**Root Cause:**
Test expects `ValidationError` when creating a deck with invalid format (`"invalid_format"`), but no error was raised. This suggests Pydantic format validation may not be enforced.

**Affected Test:**
- `tests/unit/data/schemas/test_deck.py`:
  - `test_deck_schema_invalid_format`

**Expected Behavior:**
```python
with pytest.raises(ValidationError) as exc_info:
    Deck(
        id="test-id",
        name="Test Deck",
        format="invalid_format",  # Should raise ValidationError
        ...
    )
```

**Investigation Needed:**
1. Check `src/data/schemas/deck.py` - Does `Deck.format` field have `Literal["standard", "modern", ...]` constraint?
2. If constraint missing, add Pydantic field validator:
```python
from typing import Literal
from pydantic import field_validator

class Deck(BaseModel):
    format: Literal["standard", "modern", "commander", "all"] | None

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        allowed = ["standard", "modern", "commander", "all", None]
        if v not in allowed:
            raise ValueError(f"Invalid format: {v}")
        return v
```

**Recommendation:**
High priority - format validation is critical for deck construction rules. Investigate `src/data/schemas/deck.py` and add proper validation if missing.

---

### 4. Chainlit Integration Test - Context Mocking (1 failure)

**Status:** ✅ **Test Setup Issue**
**Action Required:** Add Chainlit context mocking

**Root Cause:**
Integration test tries to call `cl.user_session.get("id")` but Chainlit context isn't initialized in test environment.

**Affected Test:**
- `tests/integration/ui/test_chainlit_agent_integration.py`:
  - `test_chainlit_message_handler_integration`

**Error:**
```
chainlit.context.ChainlitContextException: Chainlit context not found
```

**Fix Strategy:**
```python
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_chainlit_message_handler_integration():
    # Mock Chainlit context
    with patch('chainlit.user_session') as mock_session:
        mock_session.get.return_value = "test-session-id"

        # Mock cl.Message
        with patch('chainlit.Message') as mock_message_cls:
            mock_message = MagicMock()
            mock_message_cls.return_value = mock_message

            # Now test can run
            await on_message(test_message)
```

**Recommendation:**
Create a test fixture that mocks Chainlit context for all UI integration tests. Consider using `chainlit.testing` utilities if available.

---

### 5. Agent Double-Faced Card Test - Assertion Too Strict (1 failure)

**Status:** ✅ **Test Assertion Issue**
**Action Required:** Relax test assertion or update expected output

**Root Cause:**
Agent provides correct, natural language explanation of "Delver of Secrets // Insectile Aberration" but test expects literal strings "//" or "Front Face"/"Back Face" to appear in response. The agent is working correctly - it mentions "Front side" and "Back side" but not the exact phrases the test expects.

**Affected Test:**
- `tests/integration/agent/test_agent_card_lookup.py`:
  - `test_agent_double_faced_card`

**Current Assertion:**
```python
assert "//" in response or "Front Face" in response or "Back Face" in response
```

**Agent Response (correct but fails test):**
```
"Front side (Delver of Secrets)": ...
"Back side (Insectile Aberration)": ...
```

**Fix Strategy:**
```python
# More flexible assertion
assert (
    "Front side" in response or "Back side" in response or
    "//" in response or
    "transform" in response.lower()
)
```

**Recommendation:**
The agent is providing accurate information about double-faced cards. Relax the assertion to accept natural language variations like "Front side" / "Back side" instead of requiring exact "Front Face" / "Back Face" strings.

---

### 6. Runtime Warnings - Test Cleanup (4 warnings)

**Status:** ⚠️ **Test Cleanup Needed**
**Action Required:** Fix mock setup to properly await coroutines

**Affected Tests:**
- `tests/unit/ui/test_symbols.py`:
  - `test_fetch_symbols_success`
  - `test_fetch_symbols_empty_data`
  - `test_fetch_symbols_malformed_data`
  - `test_cache_initialization`

**Warning:**
```
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
response.raise_for_status()
```

**Fix Strategy:**
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_fetch_symbols_success():
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()  # Make it async
    mock_response.json = AsyncMock(return_value={"data": [...]})
```

**Recommendation:**
Low priority - warnings don't affect test results but should be cleaned up for cleaner test output.

---

## Priority Summary

### High Priority (Fix Now)
1. **Deck format validation bug** - Investigate `src/data/schemas/deck.py` to ensure format validation works

### Medium Priority (Fix Soon)
2. **Logfire config tests** - Add environment variable mocking for test isolation
3. **Visual mana symbols tests** - Batch update 13 test assertions to expect SVG HTML

### Low Priority (Cleanup)
4. **Chainlit context mocking** - Add proper context fixture for UI integration tests
5. **Agent double-faced card test** - Relax assertion to accept natural language
6. **Symbol test warnings** - Fix AsyncMock setup

---

## Recommended Actions

1. **Immediate:** Investigate deck format validation (lines 87-89 in `test_deck.py`)
2. **Next:** Update visual mana symbol test assertions (batch operation)
3. **Next:** Add environment mocking to Logfire config tests
4. **Later:** Clean up Chainlit and symbol test mocks

---

## Test Health Metrics

- **Pass Rate:** 426/446 = 95.5%
- **Visual Symbols Impact:** 13 failures (expected, feature change)
- **Real Issues:** 1-4 failures (pending investigation)
- **Test Quality Issues:** 4 failures + 4 warnings

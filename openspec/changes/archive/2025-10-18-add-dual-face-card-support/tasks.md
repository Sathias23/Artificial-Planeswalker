# Implementation Tasks

## 1. Update Card Formatters for Dual-Face Support

- [x] 1.1 Add helper function `_has_card_faces(card: Card) -> bool`
- [x] 1.2 Add helper function `_format_card_face(face: dict, face_number: int) -> list[str]`
- [x] 1.3 Modify `format_card_details()` to handle dual-faced cards
  - [x] 1.3.1 Detect if `card.card_faces` is not None
  - [x] 1.3.2 Display "**Front Face:**" and "**Back Face:**" labels
  - [x] 1.3.3 Extract and display oracle text from each face
  - [x] 1.3.4 Display mana cost and type line for each face
  - [x] 1.3.5 Fall back to root-level fields for single-faced cards
- [x] 1.4 Modify `format_card_list()` to handle dual-faced cards
  - [x] 1.4.1 Display face names in list (e.g., "Name // Name")
  - [x] 1.4.2 Show type line for both faces
  - [x] 1.4.3 Truncate oracle text appropriately for multi-face cards
- [x] 1.5 Modify `format_card_with_image()` to handle dual-faced cards
  - [x] 1.5.1 Check `card_faces[0].image_uris` if root `image_uris` is None
  - [x] 1.5.2 Extract "normal" size image from first face
  - [x] 1.5.3 Add note in image caption about back face (future enhancement)

## 2. Add Unit Tests for Dual-Face Card Formatting

- [x] 2.1 Create test fixtures for dual-faced cards
  - [x] 2.1.1 Create flip card fixture (e.g., Erayo-style card)
  - [x] 2.1.2 Create transform card fixture (e.g., Delver-style card)
  - [x] 2.1.3 Create modal DFC fixture (e.g., Sephiroth-style card)
- [x] 2.2 Test `format_card_details()` with dual-faced cards
  - [x] 2.2.1 Test flip card formatting
  - [x] 2.2.2 Test transform card formatting
  - [x] 2.2.3 Test modal DFC formatting
  - [x] 2.2.4 Verify "Front Face" and "Back Face" labels appear
  - [x] 2.2.5 Verify both oracle texts are displayed
- [x] 2.3 Test `format_card_list()` with dual-faced cards
  - [x] 2.3.1 Test list with mixed single and dual-faced cards
  - [x] 2.3.2 Verify face name formatting (e.g., "Name // Name")
  - [x] 2.3.3 Verify oracle text truncation works
- [x] 2.4 Test `format_card_with_image()` with dual-faced cards
  - [x] 2.4.1 Test with `card_faces[0].image_uris` present
  - [x] 2.4.2 Test with no image URIs (fallback to text)
  - [x] 2.4.3 Verify image element created correctly

## 3. Add Integration Tests

- [x] 3.1 Add dual-faced card query test
  - [x] 3.1.1 Search for "Sephiroth, Fabled SOLDIER" (bug report example)
  - [x] 3.1.2 Verify oracle text is returned for both faces
  - [x] 3.1.3 Verify formatted output includes both faces
- [x] 3.2 Add agent tool test with dual-faced cards
  - [x] 3.2.1 Call `lookup_card_by_name()` with dual-faced card name
  - [x] 3.2.2 Verify response includes oracle text for both faces
  - [x] 3.2.3 Verify UI elements created correctly

## 4. Update Documentation

- [x] 4.1 Update docstring in `format_card_details()` with dual-face examples
- [x] 4.2 Update docstring in `format_card_list()` with dual-face notes
- [x] 4.3 Update docstring in `format_card_with_image()` with dual-face behavior
- [x] 4.4 Add comment explaining `card_faces` data structure

## 5. Validation and Testing

- [x] 5.1 Run full test suite: `uv run pytest`
- [x] 5.2 Verify all formatter tests pass
- [x] 5.3 Run integration tests: `uv run pytest tests/integration/ -m integration`
- [x] 5.4 Manual test with Chainlit UI using dual-faced cards
  - [x] 5.4.1 Start Chainlit: `uv run chainlit run src/ui/app.py`
  - [x] 5.4.2 Search for "Sephiroth, Fabled SOLDIER"
  - [x] 5.4.3 Verify oracle text appears for both faces
  - [x] 5.4.4 Verify image displays correctly
- [x] 5.5 Run type checking: `uv run mypy src/`
- [x] 5.6 Run linting: `uv run ruff check . --fix`
- [x] 5.7 Run formatting: `uv run ruff format .`

# Change Proposal: Add Dual-Face Card Support

## Why

Dual-faced cards (flip cards, transform cards, modal double-faced cards, meld cards) do not display oracle text or images correctly. The bug report from session `221809b7-6533-4e2b-a0ae-550582b1a983` documents that searching for "Sephiroth, Fabled SOLDIER" returns only basic card information (name, type line) without the full rules text from either face of the card.

**Root Cause:** The card formatters (`format_card_details`, `format_card_list`, `format_card_with_image`) only read from the root-level `oracle_text` and `image_uris` fields. For dual-faced cards, Scryfall stores this information in the `card_faces` array, not at the root level.

**Research Findings (from Scryfall API documentation):**
- Multi-faced cards use `card_faces` array to store face-specific data
- Each face object contains: `name`, `mana_cost`, `type_line`, `oracle_text`, `image_uris`
- Root object contains shared data (e.g., `color_identity`, `cmc`, `legalities`)
- Affected layouts: `flip`, `transform`, `modal_dfc`, `meld`, `split`

## What Changes

- **MODIFY** card formatting functions to detect and handle dual-faced cards
- **MODIFY** `format_card_details()` to display both faces with clear separation
- **MODIFY** `format_card_list()` to show face names for dual-faced cards
- **MODIFY** `format_card_with_image()` to extract images from `card_faces[0].image_uris`
- **ADD** unit tests for dual-faced card formatting
- **ADD** integration tests with actual dual-faced card data (Sephiroth example)

## Impact

- **Affected specs:** `chainlit-ui` (card formatting requirements)
- **Affected code:**
  - `src/ui/formatters.py` - All three formatter functions
  - `tests/unit/ui/test_formatters.py` - New test cases
  - `tests/integration/ui/test_chainlit_agent_integration.py` - Dual-face card scenarios

**Breaking Changes:** None. This is backward-compatible enhancement.

## Research Summary

**Sources Used:**
- Scryfall API Documentation (`scryfall.com`) via Archon RAG
  - Searched: "dual-faced cards oracle text"
  - Searched: "card_faces modal flip transform"
  - Found: Card layout documentation at `https://scryfall.com/docs/api/layouts`

**Key Findings:**
1. **Card Layouts with Multiple Faces:**
   - `flip`: Cards that invert vertically (e.g., Erayo, Soratami Ascendant)
   - `transform`: Double-sided cards (e.g., Delver of Secrets)
   - `modal_dfc`: Either-side playable cards (e.g., Valki, God of Lies)
   - `meld`: Cards with meld parts on back
   - `split`: Split-faced cards (e.g., Fire // Ice)

2. **Data Structure:**
   ```json
   {
     "name": "Front Name // Back Name",
     "type_line": "Front Type // Back Type",
     "card_faces": [
       {
         "name": "Front Name",
         "mana_cost": "{2}{R}",
         "type_line": "Creature — Human",
         "oracle_text": "Front face text...",
         "image_uris": { "normal": "..." }
       },
       {
         "name": "Back Name",
         "type_line": "Creature — Avatar",
         "oracle_text": "Back face text...",
         "image_uris": { "normal": "..." }
       }
     ]
   }
   ```

3. **Implementation Pattern:**
   - Check if `card.card_faces` is not None
   - If present, iterate over faces and display each with appropriate labels
   - Fall back to root-level fields for single-faced cards

## Related Bug Reports

- Bug ID: `4861b7d1-f2b0-43a4-a2b2-784029f24cd5`
- Session: `221809b7-6533-4e2b-a0ae-550582b1a983`
- Reported: 2025-10-18T07:47:42.940600+00:00
- Example card: "Sephiroth, Fabled SOLDIER" (modal DFC from Final Fantasy crossover)

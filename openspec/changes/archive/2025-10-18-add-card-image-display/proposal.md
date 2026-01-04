# Add Card Image Display

## Why

Users requesting card information (e.g., "tell me about Burst Lightning including a card image") currently receive only text descriptions because the system does not store or display Scryfall card images. This creates a suboptimal UX where users must manually search external sites to see card visuals, breaking the conversational flow and reducing the assistant's usefulness for visual learners and deck builders who rely on card imagery.

## What Changes

- Add `image_uris` JSON field to `CardModel` to store Scryfall image URLs (small, normal, large, png, art_crop, border_crop)
- Update `Card` Pydantic schema to include optional `image_uris` field
- Modify Scryfall data import transformer to extract and store `image_uris` from bulk data
- Add `format_card_with_image()` formatter function in UI layer to display cards with Chainlit `cl.Image` elements
- Update card lookup and search tools to use new image formatter when card has image URIs
- **Migration Required:** Existing database records do NOT have image URLs and must be re-imported from Scryfall bulk data

## Impact

- **Affected specs:** data-layer, chainlit-ui, scryfall-import
- **Affected code:**
  - `src/data/models/card.py` (add `image_uris` field)
  - `src/data/schemas/card.py` (add `image_uris` to Pydantic schema)
  - `src/data/importers/transformers.py` (extract `image_uris` from Scryfall JSON)
  - `src/ui/formatters.py` (add `format_card_with_image()` function)
  - `src/agent/tools/card_lookup.py` (use image formatter when available)
  - `src/agent/tools/card_search.py` (use image formatter when available)
- **Dependencies:** Chainlit Image element API (`cl.Image`)
- **Breaking Change:** Database schema change requires re-import of all card data
- **Testing:** Manual visual testing required for image display quality

## Research Summary

Research conducted using Archon RAG on Chainlit and Scryfall documentation:

**Chainlit Image Display (source: docs.chainlit.io):**
1. **Image Element API:** `cl.Image(path=None, url=None, name=str, display="inline"|"side"|"page")`
2. **Display Options:** "inline" embeds in message, "side" shows sidebar, "page" opens fullscreen
3. **URL Support:** Can reference external URLs (perfect for Scryfall CDN images)
4. **Integration Pattern:** Attach images to messages via `elements` parameter

**Code Example Found:**
```python
import chainlit as cl

@cl.on_message
async def handle_message(msg: cl.Message):
    image = cl.Image(
        url="https://cards.scryfall.io/normal/front/...",
        name="Lightning Bolt",
        display="inline"
    )
    await cl.Message(
        content="Here's Lightning Bolt!",
        elements=[image]
    ).send()
```

**Scryfall Image URIs (source: scryfall.com):**
1. **Field Structure:** `image_uris` is a JSON object with keys: `small`, `normal`, `large`, `png`, `art_crop`, `border_crop`
2. **URL Pattern:** `https://cards.scryfall.io/{size}/front/{path}.jpg` or `.png`
3. **CDN Hosting:** Images hosted on `c1.scryfall.com`, `c2.scryfall.com`, etc. (federated CDN)
4. **Availability:** Present on all single-faced cards; for double-faced cards, image URIs are in `card_faces` array instead

**Example Scryfall `image_uris` Object:**
```json
{
  "small": "https://cards.scryfall.io/small/front/c/4/c467446b-0168-4c7d-9ab6-57ad8b664877.jpg?1562936528",
  "normal": "https://cards.scryfall.io/normal/front/c/4/c467446b-0168-4c7d-9ab6-57ad8b664877.jpg?1562936528",
  "large": "https://cards.scryfall.io/large/front/c/4/c467446b-0168-4c7d-9ab6-57ad8b664877.jpg?1562936528",
  "png": "https://cards.scryfall.io/png/front/c/4/c467446b-0168-4c7d-9ab6-57ad8b664877.png?1562936528",
  "art_crop": "https://cards.scryfall.io/art_crop/front/c/4/c467446b-0168-4c7d-9ab6-57ad8b664877.jpg?1562936528",
  "border_crop": "https://cards.scryfall.io/border_crop/front/c/4/c467446b-0168-4c7d-9ab6-57ad8b664877.jpg?1562936528"
}
```

**Research Sources:**
- https://docs.chainlit.io/api-reference/elements/image (Chainlit Image element API)
- https://scryfall.com/docs/api/cards (Scryfall Card object documentation)
- https://scryfall.com/blog (Image URI migration and CDN structure)

**Key Technical Decisions:**
1. **Use "normal" size by default** - Best balance of quality and load time (typical size ~200-300KB)
2. **Fallback to text-only** - If `image_uris` is None (old data or double-faced cards), show text description
3. **Inline display mode** - Keep images embedded in chat for seamless conversation flow
4. **No local caching** - Rely on Scryfall CDN and browser caching (simpler, no disk management)

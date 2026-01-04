# Add Card Display Formatting

## Why

Story 3.3 from the PRD requires card information to be displayed in a readable, well-formatted way in the Chainlit chat interface so users can easily understand card details at a glance. Currently, the Chainlit UI can send basic messages, but lacks structured formatting for MTG card data including proper display of card attributes, mana symbols, and multi-card results.

## What Changes

- Add structured card formatting functions that convert Card Pydantic models to formatted text displays
- Implement mana symbol representation using text/unicode (e.g., {W}, {U}, {B}, {R}, {G}, {C})
- Create list formatting for multiple card results with clear numbering/bullets
- Add Chainlit element usage (cl.Text) for structured card information display
- Implement result limiting/pagination to prevent chat overflow for large card lists (max 10-15 cards)
- Apply visual emphasis for card types and colors using markdown formatting
- Ensure all formatting follows Chainlit best practices discovered in research

## Impact

- **Affected specs:** chainlit-ui
- **Affected code:**
  - `src/ui/formatters.py` (new module for formatting functions)
  - `src/ui/app.py` (integration of formatters with message handlers)
- **Dependencies:** Chainlit elements API (cl.Text, cl.Message)
- **Testing:** Manual testing required for visual formatting quality (as specified in PRD)

## Research Summary

Research conducted using Archon RAG on Chainlit documentation (source: docs.chainlit.io):

**Key Findings:**
1. **Message Structure:** Chainlit Messages accept `content` (text/markdown) and `elements` array
2. **Element Types:** cl.Text, cl.Image, cl.File, cl.DataFrame support structured display
3. **Display Modes:** Elements support "inline", "side", "page" display options
4. **Markdown Support:** Message content supports markdown formatting for emphasis and structure
5. **Pagination Pattern:** Found DataFrame element with built-in pagination for >10 rows

**Code Examples Found:**
```python
# Structured text element example
elements = [
    cl.Text(name="card_details", content=formatted_content, display="inline")
]
await cl.Message(
    content="Card information:",
    elements=elements
).send()
```

**Research Sources:**
- https://docs.chainlit.io/concepts/element (Message elements and display modes)
- https://docs.chainlit.io/api-reference/elements/text (Text element API)
- https://docs.chainlit.io/api-reference/elements/dataframe (Pagination patterns)

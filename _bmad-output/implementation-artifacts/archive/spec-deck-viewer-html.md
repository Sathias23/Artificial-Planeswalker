---
title: 'Read-only HTML deck viewer + open-on-command script'
type: 'feature'
created: '2026-06-27'
status: 'done'
baseline_commit: '6cca63ef6167f27e9e11897a7e24cfaf60f120b9'
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/temp/design_handoff_deck_builder/Deck Viewer.dc.html'
  - '{project-root}/temp/design_handoff_deck_builder/DeckCard.dc.html'
  - '{project-root}/temp/design_handoff_deck_builder/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Decks live in `data/cards.db` with no way to *see* one. The design bundle in `temp/` specifies a polished read-only deck viewer, but it assumes a React/Electron app that does not exist in this Python+SQLite repo.

**Approach:** Ship a self-contained static HTML viewer (vanilla HTML/CSS/JS recreating the `Deck Viewer` design — Arena-style overlapping mana columns, left preview/analytics rail, no chat panel) plus `scripts/view_deck.py`, which loads a nominated deck from the DB, shapes it into the viewer's data object, injects it into the page, writes the rendered file, and opens it in the default browser. On command, Claude Code runs the script to view any deck.

## Boundaries & Constraints

**Always:** Recreate the `Deck Viewer.dc.html` look pixel-faithfully (tokens, geometry, hover-lift, click-to-feature) per the README. Use real Scryfall `art_crop` when present, gradient placeholder (keyed to card color) otherwise. Generalize the Rakdos-only palette to all WUBRG + multicolor + colorless for borders, pips, and the color pie. A deck name **or** id is required — no implicit "current" deck. Keep the pure deck→view-model transform in `src/viewer` (fully typed, `mypy --strict`, Google docstrings) so it is unit-testable without a DB. Open via stdlib `webbrowser`; render to a temp file (no repo pollution).

**Ask First:** Adding any new runtime dependency (the whole feature uses only stdlib + existing `src/data`). Persisting rendered HTML inside the repo tree.

**Never:** No editable mode, quantity stepper, chat panel, or Electron/window-control wiring (read-only `×N` badge only). No new MCP tool, no React/Electron, no `set_format`/session state. Do not modify `src/data` schemas or repositories. Do not port the `.dc.html` runtime or `support.js`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| By id | `--deck <uuid>` exists | Renders + opens viewer | N/A |
| By name | `--deck <partial name>`, one match | Resolves via `find_deck_by_name`, renders | N/A |
| Unknown deck | no id/name match | Friendly stderr msg listing available deck names; exit 1 | Non-zero exit, no browser |
| cmc bucketing | cards cmc 0,1,5,7 | 0&1→col "1", 5→"5", ≥6→"6+" | N/A |
| Lands | type_line contains "Land" | Excluded from columns/curve/avg; listed in Lands strip with color-keyed swatch | N/A |
| Multicolor card | `colors` len ≥2 | color="M": multicolor border + pie slice | N/A |
| Colorless nonland | `colors` empty | color="C": neutral border/pie slice | N/A |
| Missing art | `image_uris` null / no `art_crop` | CSS gradient fallback by color | No broken img |
| Empty mainboard | deck has 0 mainboard cards | Renders empty columns, avg "0.0", no crash | N/A |

</frozen-after-approval>

## Code Map

- `src/data/repositories/deck.py` -- `get_deck_with_cards(id)`, `find_deck_by_name(name)`, `list_decks()` (NOT re-exported from `src.data` — import from module).
- `src/data/schemas/deck.py` / `card.py` -- `Deck.deck_cards[].{quantity,sideboard,card}`; `Card.{name,cmc,mana_cost,type_line,oracle_text,rarity,colors,image_uris,card_faces}`.
- `src/data/database.py` -- `create_engine`, `create_session_factory` bootstrap (`CARDS_DATABASE_URL`).
- `temp/design_handoff_deck_builder/{Deck Viewer,DeckCard}.dc.html`, `README.md` -- source of truth for layout/tokens/interactions.

## Tasks & Acceptance

**Execution:**
- [x] `src/viewer/__init__.py` -- new package.
- [x] `src/viewer/view_model.py` -- pure `build_view_model(deck: Deck) -> dict` + helpers: `parse_mana_pips(mana_cost)`, `classify_color(card)` (W/U/B/R/G/M/C), `card_bucket(cmc)`, `is_land(card)`, `pick_art(card)` (art_crop→gradient), land-swatch + pie + curve + avgCmc derivation. Mainboard only. Match the README `Deck`/`Card` view shape.
- [x] `src/viewer/template.html` -- self-contained viewer: Google Fonts, CSS classes for card/hover-lift/selected (real `:hover`, not inline), left rail (preview, mana curve, color pie + legend), overlapping columns, lands strip; JS reads injected deck JSON, builds DOM, wires click-to-feature (default = first card). Read-only `×N` badge. Single injection placeholder (`__DECK_JSON__`) in a `<script type="application/json">` island.
- [x] `src/viewer/render.py` -- `render_html(deck: Deck) -> str`: read template, inject `json.dumps(build_view_model(deck))` (with `</`→`<\/` escape).
- [x] `scripts/view_deck.py` -- argparse `--deck` (required: id-first, then name); bootstrap session; load deck (resolve id via `get_deck_with_cards`, else `find_deck_by_name`→by id); on miss print available decks + exit 1; write `render_html` to temp file; `webbrowser.open`; print path. (`--no-open` flag added for render-only.)
- [x] `tests/unit/viewer/test_deck_view_model.py` -- cover every I/O-matrix row against `build_view_model`/helpers (no DB; construct `Deck`/`Card` schemas in-memory).

**Acceptance Criteria:**
- Given a deck name that matches exactly one deck, when `uv run python scripts/view_deck.py --deck "<name>"`, then a viewer file is written and opened showing that deck's cards in mana columns with working hover-lift and click-to-feature.
- Given a card with an `art_crop` URL, when rendered, then its frame shows the real art; given none, then the color-keyed gradient.
- Given an unknown deck argument, when run, then it prints available deck names to stderr and exits non-zero without opening a browser.

## Design Notes

View-model shape mirrors the README `Deck`/`Card` contract so the template's render logic ports directly from `Deck Viewer.dc.html`'s `renderVals()`:
```
card = {id,name,cmc,bucket('1'..'6+'),color('W'|'U'|'B'|'R'|'G'|'M'|'C'),
        typeLine,qty,rarity,pips:[...],oracle,art}
```
Pips: single-color symbols (W/U/B/R/G) → colored gradient pip (keep design's R/B values, add standard W/U/G); generic/numeric/X/hybrid → grey pip with the symbol as label. Pie/border palettes extend the design's R/B/BR set to all colors. DFC fallback: if `image_uris` is null, try `card_faces[0].image_uris.art_crop` and join face oracle text.

## Verification

**Commands:**
- `uv run pytest tests/unit/viewer/ -q` -- expected: all pass.
- `uv run ruff check src/viewer scripts/view_deck.py && uv run mypy src/viewer` -- expected: clean.
- `uv run python scripts/view_deck.py --deck "<an existing deck>"` -- expected: prints a file path and opens the viewer; manually confirm columns, hover-lift, click-to-feature, pie/curve, real art.

**Manual checks:**
- Visually compare against `temp/design_handoff_deck_builder/Deck Viewer.dc.html` (open it directly) for token/geometry fidelity.

## Suggested Review Order

**The transform (start here)**

- Entry point: pure deck → viewer data object; everything else feeds or renders this.
  [`view_model.py:269`](../../src/viewer/view_model.py#L269)
- Generalises the design's Rakdos-only palette to W/U/B/R/G/M/C.
  [`view_model.py:131`](../../src/viewer/view_model.py#L131)
- Bucketing/lands/curve/pie/avg helpers consumed by the builder.
  [`view_model.py:98`](../../src/viewer/view_model.py#L98)

**Security-sensitive paths**

- Art URL validation — rejects anything that could break out of the style attribute (review finding).
  [`view_model.py:203`](../../src/viewer/view_model.py#L203)
- Real `art_crop` vs gradient fallback selection.
  [`view_model.py:208`](../../src/viewer/view_model.py#L208)
- JSON injected into a `<script type="application/json">` island with `</`→`<\/` escape.
  [`render.py:13`](../../src/viewer/render.py#L13)

**Deck resolution & open**

- Id → exact name → unique substring; ambiguity handled (review finding), avoids `MultipleResultsFound`.
  [`view_deck.py:39`](../../scripts/view_deck.py#L39)
- Composition root: load, render, temp file, `webbrowser.open`.
  [`view_deck.py:86`](../../scripts/view_deck.py#L86)

**The view (template)**

- JS reads the injected JSON, builds the DOM, escapes all text via `esc()`.
  [`template.html:49`](../../src/viewer/template.html#L49)
- Card atom: hover-lift via CSS class, read-only `×N` badge, per-card border via `--bd`.
  [`template.html:70`](../../src/viewer/template.html#L70)
- Click-to-feature selection wiring (default = first card).
  [`template.html:219`](../../src/viewer/template.html#L219)

**Tests**

- Covers every I/O-matrix row plus the review-driven fixes (URL safety, MDFC land, pluralisation).
  [`test_deck_view_model.py:1`](../../tests/unit/viewer/test_deck_view_model.py#L1)

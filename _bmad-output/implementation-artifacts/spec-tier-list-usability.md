---
title: 'Tier list usability: in-view card preview and a readable thumbnail strip'
type: 'feature'
created: '2026-08-23'
status: 'done'
review_loop_iteration: 0
baseline_commit: '75afaf97f34e0e729569be3629c6ede0fc88893c'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The tier list agent view is unusable: thumbnails collapse to overlapping ~0px slivers (the tile's only sizing input is `aspect-ratio` on an empty box, which yields no intrinsic width), and hovering a tile sets the inspection target but the card-detail panel sits *behind* the modal scrim — hover shows nothing.

**Approach:** Inside `TierListView` only: (1) give thumbnails a real, cited size and make each tier's strip horizontally scrollable (no wrap); (2) add a lightweight, wordless, silent card-preview panel on the right of the view body — sticky inside the agent view's scroller — rendering the current inspection target (hover/focus/pin precedence stays the store's). Amend DESIGN.md **first** so every new px literal has a truthful citation. `AgentView` itself is untouched.

## Boundaries & Constraints

**Always:**
- DESIGN.md amended before CSS is written against it (inline `# AMENDED/ADDED 2026-08-23` convention).
- Preview is silent and wordless: no `aria-live`, no `role="region"`, no authored copy (preserves the zero-copy posture and the 4-live-region census). Rendered words are wire data from the card cache only.
- Preview reads `useInspectionTargetId` and never writes state.
- `position: sticky` inside `.agent-view-body` only; no new fixed layer, no `z-index`.
- No CSS nesting; no `--accent-dim`; card geometry only via the global `card-shape` class (file stays out of `CARD_SHAPED`); grid columns `minmax(0, 1fr)`, never bare `1fr`.
- No `tabIndex` on the scroll strip — the tiles are already `<button>` Tab stops; state that argument at the strip's declaration.

**Ask First:** any edit to `AgentView.tsx`/`.css`; extending the preview to Swaps/Groups views; adding flip or pin affordances to the preview.

**Never:**
- No second `CardDetail` (duplicate `id="card-detail"`, 4th live region, duplicate region/h2, double-driven deck memory).
- Don't fix GroupsView's identical collapse or SwapsView sizing here — correct their **stale comments** only where this change makes them lies.
- No new tokens (inventory is set-equality-pinned); px literals live in component CSS with DESIGN.md citations.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Hover/focus a tile | Pointer or focus on a tier tile | Preview shows that card's art, name, mana cost, type line | N/A |
| No target | Nothing hovered/focused/pinned | Preview shows the silent loading-well placeholder | N/A |
| Pinned card | Tile clicked, pointer leaves | Preview keeps the pinned card (store precedence) | N/A |
| Unknown id | Target hydrates to terminal `unknown` | Existing tile effect releases the target; preview falls back to empty | N/A |
| Art fetch fails | Image errors for target | Preview shows the named placeholder (name/cost/type) | N/A |
| ~60 cards in a tier | Long strip | Row scrolls horizontally; tiles keep full size (`flex: 0 0 auto`) | N/A |
| Narrow window | Under the shell's 1100px breakpoint | Preview column collapses away; strip stays usable | N/A |

</frozen-after-approval>

## Code Map

- `ui/src/containers/TierListView/TierListView.tsx` — `TierTile` already carries the five inspection verbs (`:200-254`); add module-local `TierPreview` + two-column body wrapper around the `<ul>`.
- `ui/src/containers/TierListView/TierListView.css` — `.tier-row-thumbs:173-177` (`flex-wrap: wrap`) → `overflow-x: auto`; `.tier-tile-thumb:208-213` (`min-height: 6lh`, the broken derivation) → explicit width; the `:200-207` comment ("width from 63:88") is false — width never derived that way.
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md` — `components.tier-row` block `:366-373` (seven values, nothing on thumb size) — add `thumb-width: 176px` (the deck grid's cited floor, `CardGrid.css:25`) + a tier-preview ruling (`preview-width: 300px`, sticky, silent, collapses ≤1100px). Row `:673` says only "a thumbnail row" — scroll contradicts nothing. `:437` (group-section) praises the content-derived route; record that it never produced a width.
- Preview data path (all already imported by this file or siblings): `state/inspection.ts` (`useInspectionTargetId`), `state/cards.ts`, `state/faces.ts`, `containers/useCardArt.ts`, `CardTile/imageUrl.ts`, `frontFaceCost.ts`. `CardDetail.tsx` is read-only reference for the placeholder ladder — DO NOT mount.
- `ui/tests/shell.test.ts` — `CONTAINERS:2363` pins exact import lists (count stays 40, no new file); px-citation gate `:1047-1055`.
- `ui/tests/keyboard-floor.test.ts` — `tier-tile` already in `WELL_CLEAR:545`; comment `:530-534` repeats the false 63:88 claim — correct; do NOT touch the tabindex enumeration `:827-838`.
- `ui/src/containers/SwapsView/SwapsView.css:129-131` — same false comment; words only.
- `ui/src/containers/TierListView/TierListView.test.tsx` — extend for preview.
- `ui/src/App.test.tsx:2258-2270` — live-region census the preview must not appear in.

## Tasks & Acceptance

**Execution:**
- [x] `DESIGN.md` — amend tier-row (`thumb-width: 176px`, strip scrolls) and add the tier-preview ruling — the citation source, written first.
- [x] `ui/src/containers/TierListView/TierListView.css` — strip: no wrap, `overflow-x: auto`, tiles `flex: 0 0 auto`; thumb `width: 176px` (cited), drop the dead `6lh` derivation + false comment; two-column body grid (`minmax(0, 1fr) 300px`, collapses ≤1100px) + sticky preview styles.
- [x] `ui/src/containers/TierListView/TierListView.tsx` — module-local `TierPreview` (reads `useInspectionTargetId`; art via `useCardArt`; `TierTile`'s placeholder ladder; wire-data words only, `alt=""`); render preview only when rows exist.
- [x] `ui/tests/keyboard-floor.test.ts` + `ui/src/containers/SwapsView/SwapsView.css` — correct the two stale 63:88 comments (words only). (Also corrected, words only, the two comments this change itself made stale: `GroupsView.css:163-167`'s citation of TierListView's now-removed derivation, and keyboard-floor's `group-tile` entry that leaned on the tier tile's old argument.)
- [x] `ui/tests/shell.test.ts` — update TierListView's `CONTAINERS` import list (`ManaCost` joins for the preview's cost pips; everything else the preview reads was already listed).
- [x] `ui/src/containers/TierListView/TierListView.test.tsx` — cover the I/O matrix rows; assert no live region/authored copy in the preview.

**Acceptance Criteria:**
- Given an open tier_list push, when the user hovers or focuses any tile, then the card's image, name, cost and type are visible in the in-view preview without closing the modal.
- Given a tier with more cards than fit, when the strip scrolls (wheel or tabbing through tiles), then tiles never shrink or overlap.
- Given the frontend gate (`npm test` in `ui/`), when it runs, then all guards pass — no new live region, tabindex, uncited px, or `CONTAINERS`/copy violation.
- Given amended DESIGN.md, when the px-citation gate reads the new literals, then each cites a value that truly exists in the tier-row/tier-preview blocks.

## Design Notes

- **Why not a second CardDetail:** duplicate skip-link id, exhaustive live-region census, duplicate region/h2, module-scope deck-memory double-driving. The preview is deliberately dumber — no pin announcement, flip, or oracle text.
- **Why module-local, not a new file:** a new containers file costs three coordinated `shell.test.ts` edits for no gain.
- **Sticky, not fixed:** `.agent-view-body` is the one scroll container; sticky inside it needs no AgentView edit and adds no fixed layer.
- **GroupsView has the identical collapse** (`GroupsView.css:172-177` cites "the tier-tile route") — untouched here; follow-up candidate.
- **The preview image ships NO fade transition** (implementation note, 2026-08-23): every image fade is an entry in `token-usage.test.ts`'s enumerated visual-transition map with an inventory-row claim, and this dumber surface ships no motion of its own rather than growing that pin — the `data-loaded` opacity flip is instant, which is also the registered reduced-motion outcome of the image-fade family. Recorded at the rule in `TierListView.css`.

## Verification

**Commands:**
- `cd ui && npm test` — expected: full vitest suite green (shell, token-usage, keyboard-floor, copy-rules, wire-contract, App census).
- `cd ui && npm run lint && npm run typecheck` — expected: clean.

**Manual checks (if no CLI):**
- jsdom proves none of the layout: real-browser check that tiles render at card size, strip scrolls, preview tracks hover/focus/pin, preview collapses at narrow width. (Retro manual-checklist item.)

## Suggested Review Order

**The design ruling (written first, everything cites it)**

- New `thumb-width: 176px` + `tier-preview` block — the citation source every px literal leans on
  [`DESIGN.md:385`](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L385)

**The in-view preview (the hover fix)**

- `TierPreview`: reads the inspection target, wordless/silent, deliberately not a second CardDetail
  [`TierListView.tsx:282`](../../ui/src/containers/TierListView/TierListView.tsx#L282)

- Hydration self-sufficiency for a cold-cache pin (review patch 2)
  [`TierListView.tsx:299`](../../ui/src/containers/TierListView/TierListView.tsx#L299)

- Two-column body: rows beside preview, only when rows exist
  [`TierListView.tsx:428`](../../ui/src/containers/TierListView/TierListView.tsx#L428)

- Sticky inside `.agent-view-body` — no fixed layer, no z-index, no AgentView edit
  [`TierListView.css:271`](../../ui/src/containers/TierListView/TierListView.css#L271)

- The ≤1100px collapse, matching the shell's own breakpoint
  [`TierListView.css:340`](../../ui/src/containers/TierListView/TierListView.css#L340)

**The strip fix (the sliver collapse)**

- Width-first sizing replaces the height-first derivation that never produced a width
  [`TierListView.css:240`](../../ui/src/containers/TierListView/TierListView.css#L240)

- Scroll, don't wrap; `flex: 0 0 auto` so tiles never crush; no-tabindex argument stated
  [`TierListView.css:198`](../../ui/src/containers/TierListView/TierListView.css#L198)

**Guards and tests**

- Rule-reading guard: the collapse cannot silently return under a green suite (review patch 1)
  [`shell.test.ts:1140`](../../ui/tests/shell.test.ts#L1140)

- Pin-over-transient pinned on this surface (review patch 4)
  [`TierListView.test.tsx:553`](../../ui/src/containers/TierListView/TierListView.test.tsx#L553)

- Face-awareness: preview follows a flipped DFC (review patch 3)
  [`TierListView.test.tsx:590`](../../ui/src/containers/TierListView/TierListView.test.tsx#L590)

- `CONTAINERS` import-list update (`ManaCost` joins)
  [`shell.test.ts:1766`](../../ui/tests/shell.test.ts#L1766)

**Peripheral truth-keeping (words only)**

- The false 63:88-width claim corrected where the fix disproved it
  [`keyboard-floor.test.ts:528`](../../ui/tests/keyboard-floor.test.ts#L528)

- Same correction in the two sibling stylesheets left behaviorally untouched
  [`SwapsView.css:130`](../../ui/src/containers/SwapsView/SwapsView.css#L130)
  [`GroupsView.css:165`](../../ui/src/containers/GroupsView/GroupsView.css#L165)

---
title: 'Story 17.5: Welcome surface — a first impression instead of placeholders and a list'
type: 'feature'
created: '2026-08-22'
status: 'done'
baseline_commit: '5ed7fb779e704694c7bcdc2972349542c54a8df9'
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The no-active-deck screen is the first thing anyone sees and it reads as unfinished: two story-key placeholder lines from the shell's c2-1 convention ("Format and size badges land here — c2-7 …", "Card detail — c4-5 — … stack here.") sit in the header and the empty right column, and the 40-odd saved deck names render as a bare vertical `<ul>` taller than the viewport.

**Approach:** Retire the shell's placeholder convention (every slot has been filled since c6-8 — the copy had "a scheduled death" and this is it), collapse the main grid to one track when the right column is empty, and make the no-active-deck surface a **Welcome** block: `docs/hero-image.jpg` as a banner above the existing state panel (copy unchanged, verbatim guard untouched), with the deck names restyled as quiet wrapping chips instead of a list.

## Boundaries & Constraints

**Always:**
- State-panel copy stays byte-identical to `EXPERIENCE.md` (`tests/copy.test.ts`). Deck names stay names-only, non-clickable, list semantics (`<ul>/<li>`, `StatePanel.test.tsx` role assertions).
- Hero is decorative: `<img alt="">`, no handlers, no `ref` (components/ posture bans). Served from `ui/public/hero.jpg` → `/hero.jpg` (favicon precedent); never hot-linked, never fetched by app code.
- Every new `px` literal in a component stylesheet cites a DESIGN.md value added in the same change (`tests/shell.test.ts` citation guard); no `--negative`/`--caution` in `StatePanel.css` (`token-usage.test.ts`).
- The other five state panels (db-not-initialized, updating, stalled, disconnected, internal-error) render exactly as today — no hero, no layout change.
- Rebuild `ui` bundle → committed `src/companion/app/static/` (now includes `hero.jpg`) and `plugin/` tree; CI/pre-commit enforce both.

**Ask First:**
- Any change to the headline/action copy strings (that is an EXPERIENCE.md ruling, not a styling one).
- Capping or truncating the deck-chip set ("+N more") — the full set is shown by default.

**Never:**
- Make deck chips clickable or add an agent-driving affordance (NG1, UX-DR33).
- Re-introduce any placeholder text naming a story key anywhere in the shell.
- Touch `src/companion` Python, the wire contract, or the deck/system stores.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First impression | Backend up, no active deck, 42 decks | Hero banner; "No deck on the glass." panel; 42 chips wrapping in rows; NO placeholder text anywhere; main is a single full-width track | N/A |
| Fresh install | No decks at all | Hero + panel, no chip row, no empty `<ul>` | N/A |
| Deck set by agent | `active_deck_changed` arrives | Welcome is replaced by the deck surface; two-column grid returns; badges render | N/A |
| Other system panel | e.g. database-updating | Plain `StatePanel` as today, no hero | N/A |
| Hero missing from bundle | `/hero.jpg` 404s | Broken-image space is not shown: `alt=""` + CSS reserves no min-height beyond the image; panel still readable | Browser-level; no app code |

</frozen-after-approval>

## Code Map

- `ui/src/components/AppShell/AppShell.tsx:169-170` -- `slot()` renders `<p class="app-shell-placeholder">` when a region is `!filled`; change to render `null`. Lines 233-236 (badges), 237 (nav), 242-248 (left), 251-256 (right), 271 (footer) are the five call sites — drop the string args. Render the second `.app-shell-column` only when `filled(right)`; add `data-single="true"` on `.app-shell-columns` in that case (attribute-as-state idiom, `data-updating` precedent `:207`).
- `ui/src/components/AppShell/AppShell.css:185-193` -- `grid-template-columns: minmax(0, 1fr) 452px`; add `[data-single] { grid-template-columns: minmax(0, 1fr) }`. Delete `.app-shell-placeholder` (`:250-254`).
- `ui/src/components/AppShell/AppShell.test.tsx:266-343` -- "placeholder copy (AC 21)" describe: rewrite as "empty regions render nothing" keeping the `false` / `[]` / empty-Fragment / empty-Set / non-empty-array cases (they guard `filled()` semantics, which survive). Add: single-column attribute present iff `right` empty; both-columns test at `:137` stays.
- `ui/tests/copy-rules.test.ts:137-146` -- `COPY_MODULES` entry text for `AppShell.tsx` describes the placeholders; update the prose (kicker, h1 fallback, "Updating…" remain).
- `ui/src/components/StatePanel/StatePanel.css:~95-105` -- `.state-panel-decks` → `display:flex; flex-wrap:wrap; gap: var(--space-2)`; `li` → chip: hairline border (1px cited to `components.welcome.deck-chip.border`), `var(--radius-pill)`, `var(--surface-well)`, **`var(--type-body)`** (14px, no uppercase/tracking companions — deck names are user data, and DESIGN.md's connection-pill ruling forbids micro's uppercase on a name), `var(--text-secondary)`, padding from spacing tokens, `max-width: 100%; min-width: 0; overflow-wrap: anywhere` so a long name wraps inside its chip rather than past the panel. Drop the `li + li` rule. Update the file-header comment that claims the panel uses only the three companion-free roles if it becomes false (with `--type-body` it stays true).
- `ui/src/components/Welcome/Welcome.tsx` (new) + `Welcome.css` -- `<div class="welcome"><img class="welcome-hero" src="/hero.jpg" alt="" /><StatePanel state="no-active-deck" decks={decks} /></div>`. Props `{ decks?: readonly string[] }`. Hero: `<img width="1536" height="1024">` intrinsic attributes (reserves the box before load — no layout shift on the first screen), `max-height: 240px` cited to `components.welcome.hero-max-height` (NOT `aspect-ratio` — `token-usage.test.ts` pins that property to `.card-shape` once), `object-fit: cover`, `object-position` cited to `components.welcome.hero-position` so the title stays visible, `var(--radius-lg)`, hairline border; block `max-width: 720px` cited to `components.welcome.max-width`; `margin: 0 auto`; `gap: var(--space-5)` between hero and panel. No motion.
- `ui/tests/shell.test.ts:1280-1300` -- import-pin list: add `{ file: 'src/components/Welcome/Welcome.tsx', imports: ['../StatePanel/StatePanel', './Welcome.css'] }` (coverage guard fires if unlisted).
- `ui/src/App.tsx:~600` -- the `surface.panel === 'no-active-deck'` arm: `<Welcome decks={system.decks} />` instead of `<StatePanel …>`. Other arms untouched. `App.test.tsx:554` (`region 'No deck on the glass.'`) still passes — the panel is inside Welcome.
- `ui/public/hero.jpg` (new) -- copy of `docs/hero-image.jpg` (1536×1024, 420 KB). Lands at bundle root unhashed (`fonts.test.ts:496` notes the mechanism).
- `_bmad-output/planning-artifacts/ux-designs/…/DESIGN.md` -- frontmatter `components.welcome:` block (`max-width: 720px`, `hero-radius: {rounded.lg}`, `hero-border`, `deck-chip` tokens) and a **Welcome** bullet after the State panel bullet (`:654`); amend that bullet's "No illustrations" to "inside the panel — the Welcome hero sits above it, not in it". `EXPERIENCE.md:64` gains "rendered as the Welcome surface (17.5): hero art above, names as quiet chips" after the existing sentence — Headline/Body untouched.
- `_bmad-output/planning-artifacts/epics-companion-app.md` (after `:3800`), `implementation-artifacts/epic-17-context.md` (Stories list), `sprint-status.yaml:753` (`17-5-welcome-surface-first-impression: …`) -- record the story as 17.4 did.
- Build: `cd ui && npm run build` → `src/companion/app/static/`; `uv run python scripts/build_plugin.py` → `plugin/`.

## Tasks & Acceptance

**Execution:**
- [x] `ui/src/components/AppShell/{AppShell.tsx,AppShell.css,AppShell.test.tsx}` -- retire placeholders; single-track grid when `right` is empty -- the two placeholder lines and the dead column go.
- [x] `ui/tests/copy-rules.test.ts` -- update `AppShell.tsx`'s `COPY_MODULES` prose -- keep the map truthful.
- [x] `ui/public/hero.jpg` -- add asset -- the image Brad asked for.
- [x] `ui/src/components/Welcome/*` + `ui/tests/shell.test.ts` pin + `App.tsx` arm -- hero above the panel on no-active-deck only.
- [x] `ui/src/components/StatePanel/StatePanel.css` -- deck names as wrapping chips -- replaces the tall list; semantics unchanged.
- [x] `DESIGN.md` + `EXPERIENCE.md` -- welcome block, citations, one EXPERIENCE sentence -- guards cite truth, not invention.
- [x] Epics file, epic-17 context, `sprint-status.yaml` -- record 17.5.
- [x] Rebuild bundle + `plugin/`; run Verification.

**Acceptance Criteria:**
- Given the companion is open with no active deck, when the page renders, then no text matching `/c[0-9]-[0-9]+/` appears anywhere on the glass, the hero image is visible above "No deck on the glass.", and the deck names read as a wrapping chip row with no link or button in the subtree.
- Given no active deck, when the DOM is inspected, then `main` contains exactly one `.app-shell-column` and `.app-shell-columns[data-single="true"]`; given a loaded deck, then two columns and no `data-single`.
- Given any other system panel, when rendered, then no `img` is in the document and the panel is unchanged.
- Given `cd ui && npm test && npm run lint && npm run build`, when run, then green and `src/companion/app/static/hero.jpg` exists; `uv run pytest -q -m "not integration"` green; `plugin/` matches the build.

## Spec Change Log

- **2026-08-22, review loop 1 (bad_spec).** Trigger: all three reviewers — deck chips rendered `ATRAXA COUNTER CABINET V2` because the Code Map prescribed `--type-micro`, whose uppercase companion is mandatory under `findRoleWithoutCompanions`, contradicting DESIGN.md's own rule that micro's uppercase may not touch a name. Amended: chip role → `--type-body`; chip overflow rules; hero intrinsic `width/height`; `hero-position` token; the `aspect-ratio` → `max-height` deviation the implementer already recorded is now the spec's text. Known-bad state avoided: uppercased user data on the first screen. KEEP: the retired-placeholder shell + `data-single` single-track grid, the `Welcome` component shape (decorative `<img alt="">` above the unchanged `StatePanel`), the test rewrites in `AppShell.test.tsx` / `App.test.tsx` / `shell.test.ts` / `attribution.test.ts` / `copy-rules.test.ts`, the DESIGN.md `components.welcome` block and Welcome bullet, the EXPERIENCE.md sentence. Do NOT add a Story 17.6 to the epics file or sprint-status — that is out of scope for this spec.

- 2026-08-22 (implementation): the hero is cropped with `max-height: 240px` (cited `components.welcome.hero-max-height`) + `object-fit: cover` instead of `aspect-ratio` — `token-usage.test.ts` pins `aspect-ratio` to `.card-shape` exactly once across the shipped tree (c4-3 AC 2). Same visual intent, and a missing file reserves no 240px hole (a hairline strip of border remains), which matches the edge-case row better. Review loop 1 applied: chips `--type-body`, hero intrinsic `width`/`height`, `hero-position` token, Story 17.6 additions removed.

## Verification

**Commands:**
- `cd ui && npm test` -- expected: green, including `copy.test.ts`, `shell.test.ts`, `posture.test.ts`, `AppShell.test.tsx`, `StatePanel.test.tsx`, `App.test.tsx`.
- `cd ui && npm run lint && npm run build` -- expected: clean; `src/companion/app/static/hero.jpg` present.
- `uv run python scripts/build_plugin.py && git status --short plugin/` -- expected: plugin tree updated, nothing else surprising.
- `uv run pytest -q -m "not integration"` -- expected: green (the static-bundle/plugin pins).

**Manual checks:**
- `uv run artificial-planeswalker companion --open` with no active deck: hero banner, panel, chips, no placeholder lines, no empty right column; then set a deck from the agent and confirm the two-column deck surface returns.
- Hero crop: the banner is 240px tall at the 720px block width, cropped `object-fit: cover` anchored at `center 20%` — the artwork's title is visible, not clipped at the top.
- Chip wrapping: with a very long deck name (say 80+ characters) the chip wraps its text inside the chip and stays within the panel; no horizontal overflow of `main`.
- Density: ~40 decks in a 1100×700 window — the chip rows wrap beneath the panel, `main` scrolls (the single scroll container), and the pinned connection pill and footer stay clear of the content.
- Missing hero: temporarily rename `hero.jpg` in the served bundle (or block `/hero.jpg` in devtools) — expect a hairline strip of border where the banner was, NOT a 240px empty hole; the panel and chips are unaffected.

## Suggested Review Order

**The Welcome surface (entry point)**

- The whole story in three lines: decorative hero above the unchanged state panel.
  [`Welcome.tsx:27`](../../ui/src/components/Welcome/Welcome.tsx#L27)

- Intrinsic `width/height` + `alt=""` — reserves the box, announces nothing, no handlers.
  [`Welcome.tsx:30`](../../ui/src/components/Welcome/Welcome.tsx#L30)

- `max-height` instead of `aspect-ratio` (token-usage pins that property to `.card-shape`).
  [`Welcome.css:20`](../../ui/src/components/Welcome/Welcome.css#L20)

- The one App arm that changed: `no-active-deck` renders `Welcome`, every other panel untouched.
  [`App.tsx:607`](../../ui/src/App.tsx#L607)

**Shell: placeholders retired, single track**

- `slot()` now renders nothing for an empty region — the c2-1 convention's scheduled death.
  [`AppShell.tsx:175`](../../ui/src/components/AppShell/AppShell.tsx#L175)

- Right column rendered only when filled; `data-single` on the grid is the state attribute.
  [`AppShell.tsx:238`](../../ui/src/components/AppShell/AppShell.tsx#L238)

- The one-track rule the attribute switches on.
  [`AppShell.css:199`](../../ui/src/components/AppShell/AppShell.css#L199)

**Deck names as chips**

- Explicit `role="list"` survives flex + `list-style:none` in Safari/VoiceOver.
  [`StatePanel.tsx:140`](../../ui/src/components/StatePanel/StatePanel.tsx#L140)

- Chip uses `--type-body`, not micro — deck names are user data, micro uppercases.
  [`StatePanel.css:134`](../../ui/src/components/StatePanel/StatePanel.css#L134)

**Design record**

- `components.welcome` block — every px/position literal in the CSS cites a value here.
  [`DESIGN.md:516`](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L516)

- The Welcome bullet; State-panel "no illustrations" narrowed to *inside* the panel.
  [`DESIGN.md:681`](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L681)

- One sentence appended; Headline/Body untouched so the verbatim guard holds.
  [`EXPERIENCE.md:64`](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L64)

**Tests & tracking**

- Placeholder describe rewritten as "empty regions render nothing"; single-column pin.
  [`AppShell.test.tsx:266`](../../ui/src/components/AppShell/AppShell.test.tsx#L266)

- Welcome surface end-to-end, no-img behind all five other panels, Welcome→deck transition.
  [`App.test.tsx:681`](../../ui/src/App.test.tsx#L681)

- `/hero.jpg` pinned as served from the bundle root (review round 2 gap).
  [`test_spa.py:375`](../../tests/unit/companion/test_spa.py#L375)

- Import-pin for the new component (coverage guard).
  [`shell.test.ts:1332`](../../ui/tests/shell.test.ts#L1332)

- Story 17.5 recorded for the retro.
  [`epics-companion-app.md:3783`](../planning-artifacts/epics-companion-app.md#L3783)

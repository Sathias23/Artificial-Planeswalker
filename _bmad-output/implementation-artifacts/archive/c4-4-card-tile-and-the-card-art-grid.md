---
epic: c4
story: c4-4
work_branch: feat/companion-c4
story_branch: feat/companion-c4-4-card-tile-and-grid
depends_on: >-
  c4-3 (merged at `b47f603`) — `.card-shape` in `src/styles/card-geometry.css` is the geometry this
  story consumes BY CLASS NAME, and `CardPlaceholder` is the component this story finally MOUNTS
  (it ships tree-shaken out of the bundle today). c4-2 (merged at `2a64231`) — `boardsOf` /
  `DeckBoards` / `surfaceOf` are the derivation and the precedence this story renders, and
  `AppShell`'s `left` slot is the hole it fills. c4-1 (merged at `2095050`) — the card cache and
  `useCardEntry`, whose production consumer this story may or may not be (Q9). Also **c3-5**
  (`GET /api/card-image/{scryfall_id}`, the route every `<img>` points at), **c3-6/c3-7/c3-8**
  (the pacer, the disk cache and the negative cache — three mechanisms this story is the first to
  exercise from a browser), **c2-7** (`Panel`, the container the grid sits in), **c2-4** (the token
  layer, whose reduced-motion registration block this story is the first to extend) and **c2-6**
  (`AppShell`, whose left-column placeholder this story displaces).
baseline_commit: b47f603
---

# Story C4.4: Card tile and the card-art grid

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad looking at my deck,
I want to see it as full card faces I can take in at a glance,
so that reading my decklist feels like looking at cards rather than at a spreadsheet.

**What this story really is.** It is the story where **the deck finally appears on the glass** —
three stories have shipped declared and unmounted, and this one mounts all of them. It is also,
measured at `b47f603`, the story where **four categories open at once**, and each of the four is a
decide-once ruling that ten to fifteen later stories inherit:

1. **`src/components/` is a CLOSED category, and this story's tile cannot join it.**
   `shell.test.ts:1257` asserts **set equality** between `git ls-files 'src/components/*.ts(x)'`
   (minus test files) and `PRIMITIVES + AppShell.tsx`. Every `PRIMITIVES` member is then held to
   `:1313-1350`: **no hook of any family** (`use[A-Z]…(`, and bare `use(`), no
   `fetch`/`WebSocket`, **no `on*` prop declaration and no `on*` JSX attribute**, no `ref` in
   either position, **no `...` anywhere**, and a type-only `react` import. A card tile needs
   `<img onLoad>` / `onError`; a grid that hydrates needs a hook. **So a new module under
   `src/components/` is red either way** — listed, the bans fire; unlisted, the coverage guard
   fires. This is not a gate to route around: it is the "category-change signal" `shell.test.ts`
   says out loud in its own prose (*"the day a primitive needs a hook it has stopped being
   presentation-only — that is a SIGNAL"*). **c4-4 is the story that answers where a stateful
   component lives** (Q1), and c4-5, c4-6, c4-7, c4-10, c4-11, c5-7, c6-5…c6-8 and c9-1…c9-3 all
   inherit the answer.

2. **This story ships the FIRST motion in the entire codebase.** Measured across every tracked
   `ui/src/**/*.css`: **zero** `transition`, **zero** `animation`, **zero** `transform`. Six
   stylesheets carry a header paragraph saying *"NO MOTION, DELIBERATELY"* and naming the reason
   (`Footer.css:18`, `ManaPip.css:44`, `ManaCost.css:6`, `StatePanel.css:19`, `Panel.css:51`,
   `CardPlaceholder.css:15` — the last of which names **this story**: *"a `transition` here would
   be pre-empting c4-4"*). So c4-4 is the first `transition`, the first `transform`, the first
   `:hover` state on anything but a footer link, the first z-index raise, and **the first
   extension of `tokens.css`'s reduced-motion registration block** — which
   `token-usage.test.ts:2172` already asserts names `c4-4` **twice** (hover pop → no scale,
   shadow only; image fade-in → instant). And the mechanism is not enough on its own: **zeroing a
   duration does not neutralise `transform: scale(1.06)`, it only makes it instant.** The block's
   own instruction covers exactly this — *"any motion that cannot be switched off by a duration
   alone — a transform, a 3D rotation, a crossfade — adds its own declaration HERE, in this block,
   in the story that builds it."*

3. **The focus ring and the live ring are composites stylelint forbids inline and the token
   inventory does not carry.** `.stylelintrc.json`'s `box-shadow` allowed-list is, verbatim,
   `none` or a comma-list of `var(--shadow-…)` / `var(--glow)` **and nothing else** — so
   DESIGN.md's `card-tile.focus-ring-over-art: '0 0 0 2px {colors.focus-ring}, 0 0 0 4px
   {colors.surface-base}'` cannot be written in a component stylesheet at all. Unlike c4-3's
   `--card-aspect`, **the value has a real DESIGN.md source** — it is just in
   `components.card-tile` rather than `components.elevation`, and `tokens.test.ts`'s inventory
   hand-lists the shadow family (`'--shadow-raise', '--shadow-rest', '--glow'`) behind a pinned
   `toHaveLength(65)`. **`ui/README.md` has already ruled the answer** and names this exact case:
   *"If you need a new composite (a live ring, a pinned ring), **add a token to the layer**; do not
   inline it, and do not declare it in your own file."* So the token is added in the open, both
   pins move together, and its value is asserted against DESIGN.md the way `--shadow-raise` is
   (Q2).

4. **The caption renders every card name in CAPITALS, by gate — and the composition reference does
   the opposite.** DESIGN.md:379 puts the caption in `{typography.label}`; DESIGN.md's `label`
   role declares `textTransform: uppercase` and `letterSpacing: 0.1em`; and
   `findRoleWithoutCompanions` **derives** from those two facts a hard requirement that any block
   applying `font: var(--type-label)` also declares `text-transform: uppercase` **and**
   `letter-spacing: var(--tracking-label)`. The mock's `CardTile` renders its `figcaption` in
   label type with **no** `textTransform` and tracking overridden to `0.02em`. The mock cannot be
   shipped; the gate wins unless DESIGN.md is amended. **This is c4-3's probe (j) in its second
   instance** — *every typography guard asks whether a role travels with its companions; none asks
   whether the role suits the value* — and it is already a declared blind-spot row in
   `ui/README.md` (Q3).

**Everything numeric below was measured on this machine at `b47f603`, read-only, against the live
database at `%LOCALAPPDATA%\artificial-planeswalker\cards.db`, the committed `openapi.json`,
DESIGN.md's frontmatter, the mock's own `_ds_bundle.js`, `.stylelintrc.json` as parsed JSON, and a
real `npm test` run. Do not rediscover it — verify it in Task 0.**

### The seam that already exists (do not rebuild any of it)

1. **The card shape is written once and is consumed by CLASS NAME, with no import.**
   `src/styles/card-geometry.css` is `@import`ed by `src/index.css`; a consumer writes
   `className="card-shape"` and inherits `aspect-ratio: 63 / 88` + `border-radius:
   var(--radius-card)`. **This story's stylesheet writes neither declaration** and joins
   `CARD_SHAPED` in `token-usage.test.ts` with its reason — at which point the converse half
   applies to it too: **no chrome radius anywhere in that file**, `--radius-md` included, which is
   precisely what the mock ships for tiles. `token-usage.test.ts:764` already says *"c4-4, c4-5
   and c4-6 join it IN THE OPEN."*

2. **The placeholder, the unknown variant and the silent well are all built, typed and tested —
   and nothing mounts them.** `CardPlaceholder` is a discriminated union: `{variant:'named-card',
   name?, cost?, typeLine?}`, `{variant:'unknown-card', cardId?}`, `{variant:'loading'}`. The
   loading member has **one property**, so a well has nothing to say with. `variant="unknown-card"
   name="Black Lotus"` **does not compile**. This story's job is to render them, not to change
   them — and `CardPlaceholder.test.tsx:359` already contains a miniature `Tile` billed as *"what
   c4-4's real tile will look like"*. Read it before writing the real one.

3. **The decklist derivation is done, once, in the store.** `boardsOf` returns
   `{commander, mainboard: CardGroup[], sideboard, commanderQuantity, mainboardQuantity,
   sideboardQuantity}`, with `mainboard` in `TYPE_GROUPS` order and empty groups omitted.
   `surfaceOf(deck, system)` already decided whether a deck or a panel is on screen. **A
   `filter(c => !c.sideboard)` in this story is the drift `deckGroups.ts` exists to prevent**, and
   its own header says why: *"so the grid and the list panel cannot disagree."*

4. **The image route is finished and this story is its first browser client.** `GET
   /api/card-image/{scryfall_id}?size=normal&face=0`. `size` is a six-member enum, `normal` is the
   default **and the grid's** (FR-19); `face` indexes **the images the card has**, not its
   `card_faces` array. Success carries `Cache-Control: public, max-age=31536000, immutable` and
   `X-Content-Type-Options: nosniff`. **No `fetch` is involved** — art reaches the screen through
   `<img src>` and the browser's HTTP cache, which is why `posture.test.ts`'s one-door list stays
   `['src/api/client.ts']` with no edit.

5. **`ui/README.md`'s blind-spot table already holds four rows written FOR this story**, by name:
   the pacer's cold-paint arithmetic, the warm-vs-cold `Content-Type` parameter divergence, the
   300-second negative-cache window, and the binary-response type lie (*"c4-4 must read the
   response as a blob and must not derive its handling from the type"* — moot if nothing fetches,
   and the record should say so). They are the four numbers that decide whether this tile looks
   broken for reasons that are not its fault.

6. **`minmax(176px, 1fr)` is pre-blessed, and the guard says so in its own advice string.**
   `shell.test.ts:342` — *"`minmax(176px, 1fr)` — c4-4's card grid — is the CORRECT form and must
   stay silent"* — with a fixture at `tests/fixtures/css/shell-violation.css:221` and a named test
   at `:1405`. The bare-`1fr` ban and the `minmax(auto, 1fr)` ban are both live; the 176px
   literal is a **geometry literal** and inherits c2-8's rule: it carries a comment citing
   DESIGN.md, and `shell.test.ts:975` runs that citation check over every `px` literal in every
   tracked stylesheet under `src/components/`.

7. **The Scryfall-host ban is waiting for this story specifically.**
   `tests/no-scryfall-hosts.test.ts:5` — *"The epic's rule is satisfied negatively in c3-5 — no
   frontend fetch code exists until c4-4 — and this scan is what keeps that true when c4-4 lands:
   the tile that renders an image must ask `/api/card-image/{id}`, never the CDN."* It is keyed on
   the host **family**, so there is no member to remember.

8. **The two vitest projects and the `tsc -b` trap, unchanged.** `src/**/*.test.{ts,tsx}` → jsdom;
   `tests/**/*.test.ts` → node; `gate-geometry.test.ts` forbids `.tsx` under `tests/`. Component
   tests are `.tsx` beside the component. `npx tsc -b --force` is what makes a cross-project
   import failure deterministic — `npm test` stays green through it. And **running
   `tests/token-usage.test.ts` alone crashes the runner** (c4-3, ledgered): prove a guard fires
   through the full `npm test`, never a single-file invocation.

### What the real data says (measured at `b47f603`, read-only)

**The grid this story actually has to draw.**

| Property | Measured |
| --- | --- |
| Decks | **40** · `deck_cards` rows **2,027** · distinct card ids across all decks **1,061** |
| Largest deck | **99 tiles** (99 distinct ids, quantity sum 100) — the whole grid is one screenful of `<img>` |
| Cards with **no image data anywhere**, among the 1,061 | **0** — the named placeholder is only ever reached **transiently** in a deck view |
| Cards with **per-face `image_uris`** (c4-6's flip control) | **27 of 1,061**; **42 of 1,986** non-sideboard rows |
| Decks with a commander / a sideboard | **16 of 40** / **5 of 40** (41 sideboard rows) |

**The quantity badge has a much smaller population than the mock implies.**

| Property | Measured |
| --- | --- |
| Rows with `quantity > 1`, all decks | **395 of 2,027** (19.5%) |
| Rows with `quantity > 1`, **the largest deck** | **1 of 99** — a Commander deck is singleton, so the badge is nearly absent |
| Largest quantity anywhere | **34** (`Swamp`), then 32, 31, 27, 25 — **all basics** |
| Consequence | the badge must fit **two digits** and must not be designed as though every tile has one |

**The caption's ellipsis is a real path, not an edge case.**

| Property (largest deck, 99 tiles) | Measured |
| --- | --- |
| Longest name | **42** (`Barkchannel Pathway // Tidechannel Pathway`) |
| Median name | **16** · shortest **5** |
| Names longer than 24 characters | **13 of 99** |
| Longest name in ANY live deck | **56** (`Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel`) |
| Longest name in the corpus | **141** (`Our Market Research Shows…Elemental`) |

At the grid's 176px floor in 11px label type at 0.1em tracking, roughly 23–24 characters fit — so
**the ellipsis fires on about one tile in eight of a real deck**, and `text-overflow: ellipsis`
plus `white-space: nowrap` plus `overflow: hidden` is load-bearing rather than defensive. (The
character-count is measured; the pixel fit is an eye-check, Task 7.)

**What the deck payload does and does not carry.** `CardSummary` is exactly
`['id','name','mana_cost','cmc','type_line','oracle_text','colors','rarity','set_code']` and
`DeckCardSummary` is `['card_id','quantity','sideboard','commander','card']`, read off the
committed `openapi.json`. **There is no image field and no `card_faces`.** Two consequences that
shape the whole component:

- **A tile cannot know in advance whether a card has artwork.** It points an `<img>` at the route
  and handles the failure. There is no pre-check and no `hydrateCard` that would supply one — a
  `Card` carries `image_uris`, but fetching 99 card records to decide whether to draw 99 `<img>`
  is the opposite of placeholder-then-fill.
- **An `<img>` error event carries NO status code and NO wire token.** So the tile cannot tell
  `404 no_image_data` from `502 image_fetch_failed` from a `503`, and — by c4-3's decide-once
  ruling #2 — **it does not need to**: *"the pixels are identical … but only this one may ever be
  retried,"* and the SPA has no per-image retry UI by design. **The named placeholder in the grid
  is reached from an `onError` event, not from `entry.placeholder`**, and that is not a violation
  of c4-3's AC 16 (no re-deriving a placeholder from a wire token) — it is a different input
  entirely. Say so in the record, because it looks like one.

**The externally-paced numbers this story is the first to feel** (from `ui/README.md`'s
blind-spot rows, measured at the C3 retrospective — verify the shape, do not re-derive):

| Fact | Measured |
| --- | --- |
| Cold deck paint | ~**99** distinct fetches · ~**99 ms** CDN latency each · pacer spacing 0.1 s → **last tile starts ~9.8 s after the first** · **8.5 MB** total (~90 KB/tile) |
| Warm deck paint | **~10.3 ms/tile** from disk, **zero** CDN requests, never enters the pacer |
| After a CDN failure | the backend answers `502 image_fetch_failed` **from memory for up to 300 s after recovery** — a tile that waits looks stuck, a tile that retries changes nothing |
| First paint against a **dead** CDN | ~**124 s** for 99 tiles (nothing is negative-cached yet) |
| NFR-05 | the 1 s budget is the **warm** render and **excludes first-fetch image paint** — the ~10 s cold paint is an expected observation, not a defect |

**The token layer and the gates, as committed.**

| Fact | Measured |
| --- | --- |
| `box-shadow` allowed value | `none`, or a comma-list of `var(--shadow-*)` / `var(--glow)` — **nothing else**, so no inline composite ring |
| Token inventory | **65**, set-equality in `tokens.test.ts:268` + `toHaveLength(65)` at `:273`; the sibling pin is `declaredTokens.size` in `token-usage.test.ts` — *"both move together or the pair is wrong"* |
| `--focus-ring` / `--focus-ring-width` / `--focus-ring-offset` | `#b3baff` / `2px` / `2px`, shipped, one consumer (`Footer.css:107`, an `outline`) |
| `--shadow-rest` / `--shadow-raise` / `--glow` | shipped, asserted against `components.elevation` byte-for-byte |
| `--motion-pulse` / `--motion-glide` | `100ms` / `240ms`; the reduced-motion block zeroes all four durations and **nothing else has ever extended it** |
| `--space-panel-gap` | `24px` — the epic's grid gap. The mock's `18px` is UX-DR5 drift and off-scale |
| `Panel` | `overflow: hidden` (`Panel.css:42`), body padding `var(--space-3)` = 12px, rest elevation `--shadow-rest` |
| `PRIMITIVES` | **17** · `COPY_MODULES` **6** · schema aliases **9** · `CARD_SHAPED` **2** |
| ESLint a11y | `jsx-a11y/no-static-element-interactions` and `no-noninteractive-element-interactions` are **errors**; inline `style={{…}}` is banned by `no-restricted-syntax` |

**The frontend gate baseline (verify it yourself in Task 0; do not trust this table).**

| Gate | Measured at `b47f603` |
| --- | --- |
| `npm test` | **1,024 passed, 42 files**, 9.5 s (run on this machine while writing this story) |
| `npm run lint` / `format:check` / `npx tsc -b --force` / `npm run build` | expected green |
| `uv run pytest -m "not integration"` | **2,447 passed, 1 skipped, 54 deselected** (c4-3's measurement; re-measure) |

> **One measurement artefact, carried forward so it is not diagnosed twice.** A `npm test` run on
> this machine has once reported `Error: Worker exited unexpectedly` with **no failing assertion**;
> the immediate re-run was green. It is a vitest worker crash, not a test failure. Re-run before
> investigating.

## Acceptance Criteria

### The category — where a component that BEHAVES lives

1. **A home is chosen for components that hold state or take handlers, and it is a RULING with a
   gate, not a directory someone picked** (Q1). `shell.test.ts:1257`'s coverage guard is a set
   equality: whatever this story adds under `src/components/` must join `PRIMITIVES` and inherit
   its bans, and the tile cannot. Whichever way Q1 goes — a second list in `shell.test.ts` with a
   different, **written-down** posture, or a new tree outside `src/components/` — the new category
   **gets its own coverage guard in this commit**, keyed on `git ls-files` like every other one.
   An uncovered directory is how the next fifteen component stories escape every gate in this
   repo at once.

2. **Exactly THREE guards are path-scoped to `src/components/`, and they are the ones a new tree
   would silently exit — measured, so the Q1 decision is made against a list rather than a
   worry.** Everything else follows the file: `token-usage.test.ts` and `shell.test.ts` both scan
   `git ls-files '*.css'` (the whole repo), `copy-rules.test.ts` scans `src/*.ts(x)`,
   `no-scryfall-hosts.test.ts` scans all of `src`, and `gate-geometry.test.ts` scans everything.
   The three that stop at the boundary are: **`shell.test.ts`'s `PRIMITIVES` coverage guard and
   its posture bans** (`:1257`, `:1280-1350`); **`posture.test.ts`'s component rules** — the
   cross-tree value-import ban and the type-only `react` import (`:197-216`); and
   **`shell.test.ts`'s `px`-literal DESIGN.md citation check** (`:994`,
   `shippedStylesheets.filter(f => f.startsWith('src/components/'))`) — which is the one that
   matters most here, because **the 176px grid minimum is exactly the literal it exists to
   police**. A new tree must replace all three or say, per guard, why not. And either way the
   **one-door rule is honoured rather than evaded**: `posture.test.ts`'s door list stays
   `['src/api/client.ts']` with **no edit** — an `<img src>` is not a `fetch`, and the record says
   so rather than leaving a reader to wonder why the first image-rendering story in the feature
   touched no network module.

### The tile

3. **The tile is the card face itself at `normal`: no frame, no title bar, no art crop, and no
   tint, overlay, gradient fade or watermark** (FR-19, UX-DR7, UX-DR14, epic AC). The `<img>`
   points at `/api/card-image/{card_id}` — **the app's own origin, always**
   (`no-scryfall-hosts.test.ts`, AD-11). `size=normal` is the route's default; whether to spell it
   anyway is a judgement, and whichever way it goes the reason is one sentence.

4. **The tile is card-shaped by CLASS, never by its own declarations** (UX-DR4, AC from c4-3's
   `card-geometry.css`). The stylesheet joins `CARD_SHAPED` with its reason, writes neither
   `aspect-ratio` nor `border-radius`, and spends **no chrome radius anywhere** —
   `--radius-md` on a tile is what the composition reference actually ships and DESIGN.md:362
   corrects it by name. Exception, stated because it will come up: the **quantity badge** is
   chrome, not a card, and DESIGN.md gives it `{rounded.pill}` — so a `--radius-pill` inside a
   `CARD_SHAPED` file is a **real collision** with the guard's second half. Resolve it (a separate
   stylesheet for the badge, or a declared exception in the guard) rather than discovering it at
   lint time.

5. **The caption sits below the art in label type, single-line with ellipsis** (UX-DR14, epic AC),
   and **the uppercase is a RULED decision, not a default** (Q3). `font: var(--type-label)` obliges
   `letter-spacing: var(--tracking-label)` **and** `text-transform: uppercase` in the same block —
   derived, not enumerated, so it cannot be dodged. The mock does the opposite. Choose, and write
   the reason where the next reader will find it: ship the uppercase caption, or amend DESIGN.md.
   Not deciding is not an option.

6. **The caption never reflows the grid and never overflows its tile.** `13 of 99` names in the
   largest real deck exceed 24 characters (measured). `white-space: nowrap` + `overflow: hidden` +
   `text-overflow: ellipsis`, and the tile's own `min-width: 0` — a grid item's default
   `min-width: auto` floors at min-content, which is the exact defect `shell.test.ts`'s bare-`1fr`
   ban exists to catch one level up.

7. **Layout renders immediately and NEVER reflows when art arrives** (UX-DR36, epic AC). The slot
   is at full size before any image exists, because the well and the `<img>` are the same 63:88
   box. The instruments available here are the two c4-3 declared and **neither is a pixel**: a
   source read, and a jsdom assertion that the element carries the class.
   `getComputedStyle(el).aspectRatio` in jsdom returns the empty string and **passes for the wrong
   reason** — the seventh recorded instance in this epic. Say which claim each instrument does and
   does not carry.

8. **An image that has not arrived shows the silent well; an image that FAILS shows the named
   placeholder; neither is ever a broken-image glyph** (UX-DR22, UX-DR36, AD-11, epic AC). Both
   come from `CardPlaceholder`, unchanged. Record the finding that **an `<img>` error event
   carries no token**, so one render answers all three backend failures — and that this is not a
   re-derivation of a placeholder from a wire token (c4-3 AC 16) but a different input.

9. **The quantity badge reads `"×N"`, pinned top-right inside `var(--space-2)`, on scrim with
   `blur(6px)` and a `1px solid var(--border-strong)` at `--radius-pill`, in the numeric role with
   its features companion** (UX-DR3, UX-DR16, epic AC; DESIGN.md `components.quantity-badge`).
   Four things this AC is really about:
   - the `×` is **U+00D7 MULTIPLICATION SIGN**, not the letter `x` — pin it byte-for-byte, because
     a keyboard produces the wrong one;
   - `font: var(--type-numeric)` **and** `font-variant-numeric: var(--type-numeric-features)` in
     the same block, or `findUnpairedNumericRole` fails by name;
   - it must fit **two digits** (`×34`, measured) and it appears on **1 tile in 99** of the largest
     real deck, so it is not the tile's dominant feature;
   - the mock's `padding: 2px 9px` is **off-scale drift** and DESIGN.md declares no padding for
     this component — derive one from `--space-*` and say which and why.

10. **The badge's accessible behaviour is DECIDED** (Q4/Q6). UX-DR16 is explicit that *"the
    accessible signals are the group-header count and the coalesced live-region announcement"* and
    the badge is garnish — but this story ships **no group header in the grid** (Q5) and no live
    region (Epic 5/c7-5). So state where the quantity is available to assistive technology, or
    state that it is only in the badge and why that is acceptable here. **Do not smuggle an
    authored string into an `aria-label`** without joining `COPY_MODULES`: `copy-rules.test.ts`'s
    attribute half collects *every* literal reaching `aria-label`, `alt`, `title` and six others,
    **whatever its shape**.

11. **The card name is announced ONCE** (Q4). UX-DR48 keeps `alt={name}` on grid tiles *"because
    there the image is the only carrier"* — and for this component **that justification is
    measurably false**, because UX-DR14 puts the same name in a caption directly beneath it. With
    the tile a focusable control, its accessible name is the concatenation of both. Rule it, in the
    open, against UX-DR48's own logic for row thumbnails (*"use `alt=""` — the name is announced
    once, from the row text"*), and record which story's test proves it.

### The grid

12. **The grid is `repeat(auto-fill, minmax(176px, 1fr))` with a 24px gap, and reflows at any
    supported width** (UX-DR4, UX-DR8, epic AC). `176px` is a geometry literal carrying its
    DESIGN.md citation within a sentence of the value (`shell.test.ts:975` runs the proximity check
    over every `px` literal in every component stylesheet). The gap is `var(--space-panel-gap)` /
    `var(--space-5)` — **the mock's 18px is UX-DR5 drift**, off-scale, and a lint error.

13. **The grid is `ul`/`li`** (UX-DR44, EXPERIENCE.md:154). Not a `div` soup, and not a `role`
    attribute painted onto one. If a list-style reset is needed, it is in this story's stylesheet
    with a reason.

14. **What the grid renders from `DeckBoards` is RULED, and the ruling covers the commander and
    the sideboard** (Q5). The composition reference shows **one flat grid in one `Panel`** titled
    `Maindeck · 60 cards · 16 distinct`; EXPERIENCE.md's Flow 1 says a new card *"appears in its
    type group"*; c4-2 derived `mainboard: CardGroup[]` in `TYPE_GROUPS` order **and** a separate
    `commander` board **and** a `sideboard`, measured at 16 and 5 decks respectively. Three real
    populations, and "not mentioned" would silently drop 41 sideboard rows and 16 commanders off
    the glass. **Whatever is not rendered here is named with the story that renders it.**

15. **The order the grid draws is the store's, not a second sort.** `TYPE_GROUPS` order and
    `boardsOf`'s partition are already derived once *"so the grid and the list panel cannot
    disagree"*. A `sort()`, a `filter(c => !c.sideboard)` or a second grouping in this story is the
    drift `deckGroups.ts` was written to prevent (AD-12).

16. **The grid mounts into `AppShell`'s `left` slot, displacing the placeholder rather than
    deleting it** (the c2-9 decide-once ruling, fourth application). `AppShell.tsx` is **not
    edited**: its placeholder still fires whenever `left` is empty and `AppShell.test.tsx` still
    asserts it against the component's own props. `App.test.tsx:405-408` currently asserts *"The
    card-art grid lands here — c4-4"* is visible **with a deck loaded** — that assertion changes in
    this commit, and changing it is the point.

### Motion, focus and reduced motion

17. **Hover or keyboard focus scales the tile 1.06 in place and raises its z-index so neighbours
    slide under, over `--motion-glide` with `--ease-glide`** (UX-DR14, DESIGN.md
    `components.card-tile`, epic AC). **Presentation only: it never changes hit targets** — a
    `transform` does not affect layout or hit testing, which is why the spec says "in place", and
    growing the element with `width`/`padding` instead would violate the AC while looking
    identical. The raised z-index must stay **below the overlay layer's 20** (`AppShell.css:237`,
    UX-DR38).

18. **`prefers-reduced-motion: reduce` removes the SCALE, not just the duration, and the fallback
    is REGISTERED in `tokens.css`'s block** (UX-DR42, epic AC). Zeroed durations make the scale
    instant, not absent; UX-DR42's named fallback is *"no scale, shadow only"*. The registration
    block's own instruction is that a motion a duration cannot switch off *"adds its own
    declaration HERE, in this block, in the story that builds it"* — and
    `token-usage.test.ts:2172` already asserts the block names `c4-4`. **Image fade-in is the
    other half**: `transition: opacity var(--motion-pulse)` IS neutralised by the zeroed duration,
    so it needs the mechanism and not a second declaration — say which of the two fallbacks is
    mechanical and which is explicit, rather than treating them the same.

19. **Nothing pulses, loops or alternates, at any setting.** `animation-iteration-count` may only
    be `1`; `infinite` and `alternate` are banned in every spelling by stylelint **and** by a guard
    that parses the `animation` shorthand's comma-separated list. A literal duration anywhere in a
    `transition`/`animation` is a lint error — durations come from `--motion-*`, easings from
    `--ease-*`, and `0s`/`0ms` stay legal.

20. **Tiles are focusable, in the Tab order in visual order, and use the focus-ring-over-art
    treatment** (UX-DR14, UX-DR40, UX-DR41, UX-DR47, epic AC). **A real `<button>`, not a
    `tabIndex` on a `div`** — UX-DR47 is unconditional and `jsx-a11y/no-static-element-interactions`
    is an ESLint **error**. A `<button>` with no `onClick` in this story is correct and lint-clean;
    **c4-5 adds the handler**, and c4-11 owns the skip link and the tab-order floor. `:focus-visible`,
    not `:focus` — the shipped idiom is `Footer.css:107`, and nothing may write `outline: none` in
    any spelling.

21. **The focus ring (and the live ring, if this story ships it) come from a TOKEN, added in the
    open** (Q2). The composite cannot be inlined — stylelint's allowed-list admits only
    `var(--shadow-*)`/`var(--glow)` — and `ui/README.md` already rules that a new composite is a
    token. Adding one moves `expectedNames`, `tokens.test.ts`'s `toHaveLength(65)` **and**
    `token-usage.test.ts`'s `declaredTokens.size` **together**, and the value is asserted against
    DESIGN.md's `components.card-tile` entry the way the three elevation tokens are asserted
    against `components.elevation`. Whether the **live ring** ships at all is a boundary call —
    nothing sets `live` until c4-5 — and either answer is fine with a reason.

### Volume, pacing and the things that will look like defects

22. **A 99-tile cold paint is designed for, with the numbers in hand** (`ui/README.md`'s four
    c4-4-facing blind-spot rows; the ledger entries homed here). The tile must not show a spinner,
    must not time out, and must not retry in a loop — the backend answers a remembered failure
    from memory for up to 300 s and *"a tile that retries in a loop will be answered from memory
    and change nothing"*. **Whether all ~99 `<img>` mount at once or are deferred (`loading="lazy"`,
    `decoding="async"`, `fetchpriority`) is a real decision with a measured cost** (Q7): it is the
    single lever this story has over the pacer-queue entry re-homed here at c4-1.

23. **`ui/README.md`'s four blind-spot rows written for this story get a disposition each**: the
    pacer arithmetic, the warm-vs-cold `Content-Type` parameter, the 300 s negative-cache window,
    and the binary-response type lie. For each: honoured, made moot (say why), or re-homed by name.

### Boundaries — what this story must not do

24. **No inspection, no pin, no hover→detail-panel wiring, no unpin, no pinned ring** — the
    inspection contract is **c4-5's**, and the tile ships a `<button>` with no handler so that
    c4-5 adds one rather than reshaping the component. **No flip control and no `face` parameter**
    — **c4-6's** (and it owns the tile's top-left, which the badge must never occupy). **No deck
    list, no group headers in the right column** — **c4-7's**. **No curve, no colour bar, no format
    check** — c4-8/c4-9/c4-10. **No skip link and no focus management** — **c4-11's**. **No
    empty-deck line** — **c4-12's** (EXPERIENCE.md:70 gives the copy; do not pre-empt it, and do
    not crash on a zero-card deck either). **No `deck_changed` refetch, no shimmer, no quantity
    glow, no live-region announcement** — Epic 5 and c7-5.

25. **`AppShell.tsx`, `CardPlaceholder`, `states.ts`, `cards.ts`, `deck.ts`, `deckGroups.ts` and
    the seventeen listed primitives are untouched as SOURCE.** `CardPlaceholder` gains its first
    **consumer**, not an edit. If any of them genuinely needs a change to be consumable, that is a
    finding to record with its argument, not a quiet edit.

26. **No new dependency, no second state or data-fetching library, no image-fetching code, no
    second code generator** (AD-12), asserted by `package-contract.test.ts`. **No wire change** —
    every shape this story renders already ships; if nothing under `src/` changes but the built
    bundle, the five Python gates are byte-identical to baseline and the record says so.

27. **No inline `style={{…}}`, ever** — ESLint bans the attribute, and it is the one hole through
    which the entire token layer can be bypassed. If a runtime value is genuinely needed (a
    computed grid template, a bar height), that is a rule change argued in the open, not a local
    exception.

### The gates, the artifacts and the ledger

28. **Every `deferred-work.md` entry homed on `c4-4` is enumerated with a disposition each** (C2
    retro ruling **R2**: inherited deferrals are ACs *at context time*). They are listed in §"The
    inherited deferrals" below. For each: **implement**, **re-home by name**, or **decline with a
    reason**. "Not mentioned" is a failure of this AC.

29. **Every AC above has a test, in the project that can see what it asserts.** Component tests are
    `.tsx` beside the component (jsdom); guard tests belong in `ui/tests/` (node) and must respect
    the `tsc -b` cross-project import trap. **State plainly which claims are NOT machine-checkable
    here** — the pixel ones, the "does it look like a card" ones, the ~10 s cold paint — and where
    they land instead. An undeclared limit reads as coverage.

30. **Evasion probes, in the manner this epic has established.** For each new guard or contract,
    write the probe that *should* defeat it and prove it does not; record every probe **including
    any that passed** — c4-3's probe (j) passed and was the most valuable line in that record. At
    minimum: (a) a stateful component added to the new category's directory **without** joining its
    list; (b) a chrome radius written into the tile's stylesheet; (c) the tile's `aspect-ratio`
    written locally instead of consumed from `card-shape`; (d) the caption's `text-transform`
    deleted while its tracking stays; (e) `transform: scale(1.06)` left un-neutralised under
    reduced motion; (f) a literal `240ms` in the transition; (g) an `<img src>` pointed at
    `cards.scryfall.io`; (h) the badge's `×` swapped for the letter `x`; (i) a bare `1fr` grid
    track; (j) a new shadow token added to `tokens.css` **without** moving the sibling pin in
    `token-usage.test.ts`.

31. **The SPA bundle and the `plugin/` mirror are rebuilt and their change is MEASURED.**
    `npm run build` writes into `src/companion/app/static/` — **it mutates `src/`** — and
    `scripts/build_plugin.py` regenerates the mirror; CI drift-checks both. Record before/after
    hashes. **This is the story where the JS bundle finally grows**: c4-3's was byte-identical
    because nothing imported `CardPlaceholder`, and this commit imports it. Report both halves.

32. **All five frontend gates and all five Python gates are green at the end, with counts recorded
    before and after.** `npm run lint`, `format:check`, `npx tsc -b --force`, `npm test`,
    `npm run build`; `uv run pytest`, `ruff check`, `ruff format --check`, `mypy src/`,
    `mypy src/ --platform win32`.

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (AC 32; standing agreement)
  - [x] Confirm `origin/feat/companion-c4` is at **`b47f603`**; cut
        `feat/companion-c4-4-card-tile-and-grid` from it
  - [x] Run and record with **durations**: `uv run pytest -m "not integration"` (expect **2,447
        passed, 1 skipped, 54 deselected**), `ruff check`, `ruff format --check`, `mypy src/`,
        `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (expect
        **1,024 passed, 42 files**), `npm run build`. On a `Worker exited unexpectedly` with no
        failing assertion, re-run before investigating
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*`, `index.html` and the
        `plugin/` mirror (AC 31)
  - [x] **Verify §"What the real data says" yourself** — at minimum the 99-tile largest deck, the
        `395 / 2,027` quantity population, the `1 of 99` badge population in that deck, the
        `13 of 99` names over 24 characters, and the `0 of 1,061` with no image data. If any has
        changed, the ACs that rest on it change with it
  - [x] **Read, in this order:** `ui/tests/shell.test.ts:1109-1360` (the closed category — this is
        Q1's whole argument), then `src/components/CardPlaceholder/CardPlaceholder.{tsx,test.tsx}`
        (especially the `Tile` exemplar at `:347-440`), then `src/state/deckGroups.ts` and
        `src/state/deck.ts`'s `surfaceOf`, then `src/styles/card-geometry.css`, then
        `ui/tests/token-usage.test.ts`'s `CARD_SHAPED` block and `:2100-2185`, then
        `ui/README.md`'s blind-spot table (the four c4-4 rows). They are the specification

- [x] **Task 1 — Answer Q1 BEFORE writing a component, and build its coverage guard** (AC 1, 2)
  - [x] Decide where a component that holds state or takes handlers lives, and write the argument
        where the next author will read it (`ui/README.md`, beside "The presentation-only
        primitives")
  - [x] Build the new category's **git-derived** coverage guard in the same commit, with the
        posture it *does* have written down (what it may hold, what it still may not)
  - [x] Prove the guard fires: probe (a) — a module in the new tree that never joins the list
  - [x] Confirm `posture.test.ts`'s door list needs **no** edit, and state why an `<img src>` is
        not a network door

- [x] **Task 2 — The tile** (AC 3, 4, 5, 6, 7, 8, 9, 10, 11)
  - [x] The `<img>`, the well behind or beside it, the `onError` swap to `CardPlaceholder`, the
        fade over `--motion-pulse` (Q8)
  - [x] The caption, with Q3 ruled and the ruling recorded **in the CSS**
  - [x] The quantity badge, with the `×` pinned byte-for-byte and the AC-4 `--radius-pill`
        collision resolved
  - [x] Rule Q4 (the double announcement) and Q6 (what the badge exposes), and test the tile's
        accessible name for real

- [x] **Task 3 — The grid and the mount** (AC 12, 13, 14, 15, 16)
  - [x] The `ul`/`li` grid, `minmax(176px, 1fr)` with its DESIGN.md citation, `--space-panel-gap`
  - [x] Answer Q5 — flat or type-grouped — and give the commander and the sideboard an explicit
        home or an explicit named owner
  - [x] Fill `AppShell`'s `left` slot from `App.tsx`; update `App.test.tsx`'s displacement
        assertion and leave `AppShell.tsx` byte-pristine
  - [x] Answer Q9 (does anything here subscribe to `useCardEntry`, or does the grid read the
        board it was handed?) and Q10 (does the empty-deck case reach this story at all)

- [x] **Task 4 — Motion, focus, and the reduced-motion registration** (AC 17, 18, 19, 20, 21)
  - [x] Add the ring token(s) to `tokens.css` (Q2), move **both** pins, and assert the value
        against DESIGN.md's `components.card-tile` block
  - [x] The hover/focus scale, the z-index raise below 20, `:focus-visible`, and the
        focus-ring-over-art
  - [x] Extend the reduced-motion block with the scale fallback; prove the image fade is
        neutralised by the zeroed duration alone and say so
  - [x] Probes (d), (e), (f)

- [x] **Task 5 — Volume and pacing** (AC 22, 23)
  - [x] Answer Q7 (`loading="lazy"` and friends) with the pacer arithmetic in hand, and record
        what the choice costs and buys
  - [x] Give each of `ui/README.md`'s four c4-4 blind-spot rows a disposition
  - [x] Probe (g) — an `<img>` pointed at the CDN

- [x] **Task 6 — Evasion probes, and the declared limits** (AC 29, 30)
  - [x] Before the probes: write down, per AC, **which claims this suite cannot carry** — the
        pixel ones, "does it look like a card", the ~10 s cold paint, the warm-cache `onLoad`
        race — and where each lands instead (Task 7, or the epic manual-testing checklist). An
        undeclared limit reads as coverage
  - [x] Probes (a)–(j) at minimum; record every probe and its outcome, **including any that
        passed**. Run each through the **full** `npm test` — a single-file invocation of
        `tests/token-usage.test.ts` crashes the runner and reports a guard as firing when nothing
        asserted (c4-3, ledgered)

- [x] **Task 7 — The eye-check this story cannot avoid** (AC 7, 29; the c4-3 re-home)
  - [x] **A real browser, a real deck, a real backend.** This is the first story with something to
        look at, and c4-3 re-homed its composition half here **by name**: does a placeholder sit
        correctly beside a real card face in a real grid, at the same footprint?
  - [x] The named cases: the 42-character name at the 176px floor (ellipsis), the `×34` badge, the
        hover pop at the panel's edge (`Panel.css:42` is `overflow: hidden` with 12px padding — a
        1.06 scale grows 5.3px horizontally and 7.4px vertically per side, and `--shadow-rest`'s
        `0 12px 32px` extends further and **will** be clipped), the focus ring over both a light
        and a dark card face, and the cold paint's ~10 seconds
  - [x] The uppercase caption (Q3) against a real screen, because that is where the decision is
        actually made

- [x] **Task 8 — The ledger, the docs and the artifacts** (AC 23, 28, 31, 32)
  - [x] Give each inherited deferral a disposition (AC 28)
  - [x] Update `ui/README.md`: the new component category and its posture, the card-shape
        consumer note, the reduced-motion extension, the ring token, the grid's geometry literal,
        and any new blind-spot rows
  - [x] Rebuild the bundle and the `plugin/` mirror; record before/after hashes (AC 31)
  - [x] Re-run all ten gates; record counts and durations

### Review Findings

Three-layer review 2026-08-04 (Blind Hunter / Edge Case Hunter / Acceptance Auditor); 28 raw
findings, deduped to 21 + 3 dismissed (container `.setState` and `fetch` regex weaknesses — both
already covered repo-wide by `store-writes.test.ts` and `posture.test.ts`'s name-presence
machinery; the untracked `graphify-out/` dir — outside the diff, keep it out of the commit).

- [x] [Review][Decision→Patch] **Task 7's cold-paint eye-check is ticked but was never
      performed** — RULED 2026-08-04: perform it now. Clear the backend image disk cache, one real
      cold paint of the 99-card deck in a browser, record the observation, and re-check
      disposition 8 (dead-CDN escalation) against what is actually seen. (medium)
- [x] [Review][Decision→Patch] **The copy-rules empty-attribute narrowing is broader than its
      motivating case** — RULED 2026-08-04: restrict the exemption to `alt` (trimmed-empty =
      absence, for `alt` only). An empty `aria-label`/`title` is collected again, so the
      antipattern is flagged rather than blessed; the silent-half fixtures move to `alt`-only
      spellings. (low) [ui/tests/copy-rules.test.ts:325]

- [x] [Review][Patch] **`settleIfCached` settles a cached SUCCESS but not a cached FAILURE** — a
      failure that lands before React attaches `onError` (instant negative-cached 502 — the mirror
      of the race the header documents as the normal path) leaves `complete && naturalWidth === 0`
      and the tile stuck on the silent well forever; the `failed` arm is unreachable from the
      cached path (high-value medium) [ui/src/containers/CardTile/CardTile.tsx:175-178]
- [x] [Review][Patch] **The transform-neutralisation guard accepts an inert no-`!important`
      registration** — `declarationsIn` strips `!important` before the guard reads values, so a
      future story registering `transform: none` WITHOUT `!important` (which tokens.css's own
      comment measures as a cascade no-op) passes; the firing half only ever tests the
      `!important` spelling (high) [ui/tests/token-usage.test.ts:2215-2241, 244-255]
- [x] [Review][Patch] **Same guard is blind to the individual transform properties** — `scale:`,
      `rotate:`, `translate:` are real shipped CSS and `scale: 1.06` is the idiomatic spelling of
      this story's own hover pop; `property !== 'transform'` waves them through, reopening probe
      (e)'s hole under another spelling (medium) [ui/tests/token-usage.test.ts:2219]
- [x] [Review][Patch] **The "does not re-arm the error" test never re-renders** —
      `fireEvent.click` on a handler-less button triggers no state change and no re-render, so the
      assertion passes because nothing happened; use RTL `rerender()` (medium)
      [ui/src/containers/CardTile/CardTile.test.tsx:176-184]
- [x] [Review][Patch] **AC 12's positive claims have no positive assertion anywhere** — nothing
      asserts `repeat(auto-fill, minmax(176px, 1fr))` is the shipped track or that the gap is
      `var(--space-panel-gap)`; `shell.test.ts` only bans bad forms, yet `CardGrid.test.tsx`'s
      header claims those are "SOURCE claims, asserted in tests/shell.test.ts" — a mis-declared
      limit reads as coverage (medium) [ui/src/containers/CardGrid/CardGrid.test.tsx header;
      ui/tests/shell.test.ts]
- [x] [Review][Patch] **Probe (a)'s committed firing half is a tautology** — it asserts that
      appending to an array changes it, exercising neither `git ls-files` nor the coverage
      comparison; restructure so the actual guard logic is fed the planted module (low)
      [ui/tests/shell.test.ts:1578-1585]
- [x] [Review][Patch] **The wire-token boundary test asserts on its own fixture** —
      `Object.keys(BLACK_LOTUS)` can never contain `placeholder`/`reason` by construction; a
      type-level assertion on `CardTileProps` is the strong form (low)
      [ui/src/containers/CardTile/CardTile.test.tsx:165-174]
- [x] [Review][Patch] **App.test's own-origin img loop is vacuous when zero `<img>` render** —
      assert the image count before iterating (low) [ui/src/App.test.tsx:439-441]
- [x] [Review][Patch] **ArtState never resets when `cardId` changes on a mounted tile** — a
      `failed` tile keeps the placeholder for a different/recovered card; today's only call site
      keys by `card_id`, so either add a reset effect keyed on `cardId` or document the
      key-remount contract on `CardTileProps` (low)
      [ui/src/containers/CardTile/CardTile.tsx:164-186]
- [x] [Review][Patch] **The recorded jsdom accname spelling contradicts ID order** — the record
      says the run-together artefact is `×4Black Lotus` (test comment + README blind-spot row),
      but accname follows `aria-labelledby` ID order (`captionId badgeId` → `Black Lotus×4`);
      measure once and correct whichever statement is false (low)
      [ui/src/containers/CardTile/CardTile.test.tsx:352; ui/README.md:1128]
- [x] [Review][Patch] **AC 31's before/after SHA-256 hashes are not in the record** — only byte
      sizes were recorded; compute pre-change hashes from `git show HEAD:` and post-change from
      the tree, write both into the Dev Agent Record (low)
- [x] [Review][Patch] **The three new README blind-spot rows are detached from the table** — a
      blank line at README:1127 plus no header row means they render as plain pipe-text, not
      table rows (low) [ui/README.md:1127-1130]
- [x] [Review][Patch] **`deferred-work.md` entry 5 claims "RESOLVED, structurally" above what the
      code carries** — the resolution ("every tile is a button named by its caption") has two
      admitted corners: the nameless-card branch ships an unnamed focusable button (pinned by
      test), and the actual announcement is jsdom-unverifiable; soften the disposition to carry
      both (low) [_bmad-output/implementation-artifacts/deferred-work.md entry 5]
- [x] [Review][Patch] **CardGrid's conservation test encodes the fixture as magic arithmetic** —
      `boards.commander.length + 4 - 1` restates the fixture instead of deriving from `MIXED`
      /`boards.mainboard` the way the neighbouring test does (low)
      [ui/src/containers/CardGrid/CardGrid.test.tsx:109]
- [x] [Review][Patch] **The guard's non-vacuity message lies for two of its three triggers** —
      `expect(moving.length, 'no stylesheet declares a transform…').toBe(2)` shows that message
      at counts 1 and 3 too; split into `toBeGreaterThan(0)` (that message) + the enumerated pin
      (its own update-the-list message) (low) [ui/tests/token-usage.test.ts:2234]
- [x] [Review][Patch] **Prose says the transform guard needs "no edit" for c4-6/c6-5; the
      enumerated pin guarantees one** — the derived half is edit-free but `toBe(2)` +
      `toEqual([...])` fire on any correctly-registered new transform; reword the README/doc-block
      claim to name the pin (low) [ui/tests/token-usage.test.ts:2234-2238; ui/README.md motion
      section]
- [x] [Review][Patch] **Container `withoutComments` eats code after `//` inside a string** — the
      `'X // Y'` double-faced-name idiom this component traffics in deletes the rest of the line
      before the import/ban regexes run; mask string literals first (repo-wide guards cover the
      material bans, but the declared-imports check is exposed) (low)
      [ui/tests/shell.test.ts:1496-1497]
- [x] [Review][Patch] **Permitted-roots filter accepts path-traversal specifiers** —
      `'../../state/../api/client'` passes `^\.\.\/\.\.\/(?:components|state)\/`; normalize before
      matching (low) [ui/tests/shell.test.ts:1540-1546]
- [x] [Review][Patch] **Container coverage guard exempts any shipped module named `*.test.ts`** —
      a runtime module with a test-shaped filename joins no list and is held to no posture; assert
      excluded files actually import vitest (low) [ui/tests/shell.test.ts:1519]

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

1. **The two image tokens render IDENTICALLY and are still two tokens** (c4-3 ruling #2,
   `states.ts:111-116`): `no_image_data` is permanent, `image_fetch_failed` is transient and
   negative-cached with backoff. *"The pixels are identical … but only this one may ever be
   retried."* One render for both is correct — and from an `<img>` the tile cannot tell them apart
   anyway.

2. **AD-11 / the backend's own promise:** never a grey rectangle, a 1×1 pixel or a generic card
   back. `test_routes_card_image.py` holds the backend to it; the client half is a placeholder the
   tile draws from data it already has.

3. **The primitive posture** (c2-9 Q4): presentation-only means no hook of any family, no `fetch`,
   no handler, no `ref`, **no spread**, and a type-only `react` import. This story does not weaken
   that — it decides where the components that cannot satisfy it live.

4. **Geometry literals are a named non-ban with a condition** (c2-8): allowed *provided the
   citation is true*. `176px` has a true citation (`UX-DR4`, DESIGN.md:344/362). `blur(6px)` has
   one (`components.quantity-badge.backdrop`). The mock's `18px` gap and `2px 9px` badge padding
   have none — they are UX-DR5 drift and the spacing rule is a lint error, not a preference.

5. **Emptiness is `filled()`, never truthiness; a number is `Number.isFinite`, never `count &&`**
   (c2-7, review 2026-07-29). `{quantity && <Badge/>}` renders the bare string `0`; `quantity ? …`
   drops a real zero. The quantity threshold here is `> 1`, which is neither.

6. **`--accent-dim` is banned on `--surface-overlay`** (2.70:1, UX-DR6) — and the guard is
   **same-block only**. The mock uses `accent-dim` for the tile's live border; DESIGN.md corrects
   it to `accent` by name, *"because tiles also appear on `surface-overlay` inside agent views."*

7. **The composition reference is read for arrangement and density, never for rules**
   (DESIGN.md:366). Measured, this story's mock is wrong in five specific places: `--radius-md`
   instead of the card radius, a 1:1.400 aspect instead of 63:88, an 18px gap instead of 24, `2px
   9px` badge padding off the scale, and a caption in label type with the uppercase silently
   dropped. Four of the five are lint or gate errors; the fifth is Q3.

### Latest technical specifics — React 19.2, and the two `<img>` traps

The stack is pinned and this story adds nothing to it: **React `^19.2.8`**, **zustand `^5.0.14`**,
TypeScript pinned `>=5.9 <6.1` with its two measured reasons in `package.json` itself. Three
version-specific facts matter to a component whose whole job is an `<img>`:

- **`fetchPriority` is camelCase in React 19** (React 18 passed it through as an unknown attribute
  and warned). `decoding` and `loading` are lowercase DOM attributes React passes through
  unchanged. Getting the casing wrong is a silent no-op plus a console warning, not a build error
  — so if Q7 reaches for any of them, assert the rendered attribute rather than the prop.
- **A cached image can finish loading before React's `onLoad` is attached.** This is not a
  hypothetical here: a successful image is served with `Cache-Control: public, max-age=31536000,
  immutable`, so **every render after the first is a browser-cache hit** and the `load` event can
  fire during element creation. A tile that only ever leaves the "loading" state from an `onLoad`
  callback would then show a silent well forever on exactly the path NFR-05's one-second warm
  render describes. The standard mitigation reads `HTMLImageElement.complete` on mount — which
  needs a `ref`, which is another reason the tile cannot be a listed primitive (Q1). **Verify this
  against a real browser with a warm cache in Task 7**; jsdom loads no images and fires no `load`
  event, so this suite cannot see it in either direction.
- **`onError` fires once per `src`.** A re-render with the same `src` after a failure does not
  re-arm it, which is the correct behaviour here — the backend answers a remembered failure from
  memory for up to 300 s and *"a tile that retries in a loop will be answered from memory and
  change nothing"* — but it means the error state must survive re-renders rather than being
  recomputed.

### The fifteen things this story must not break

1. `shell.test.ts`'s **git-derived coverage guard** (`:1257`) — set equality over
   `src/components/`. Whatever this story adds there must join `PRIMITIVES`; whatever it adds
   elsewhere needs its own guard (AC 1).
2. `shell.test.ts`'s per-primitive bans (`:1280-1350`) — exhaustive import lists, hooks by family,
   `on*` in both positions, `ref` in both positions, rest/spread, non-type `react` import.
3. `shell.test.ts`'s **bare-`1fr` / content-floored-`minmax` ban** (`:335-410`) and its
   **DESIGN.md citation proximity check over every `px` literal** (`:975`).
4. `shell.test.ts`'s root-clipping ban and the single-full-window-overlay guard.
5. `posture.test.ts`'s exhaustive network-door list (`:328`) and the cross-tree value-import rule
   (`:197-206`).
6. `token-usage.test.ts`'s `CARD_SHAPED` allowlist — **both** halves plus the markup scan — the
   nesting ban, `findRoleWithoutCompanions`, `findUnpairedNumericRole`, `findAccentDimInOverlayFile`,
   the pulse/loop ban, the `--mana-*` data-ink allowlist, `declaredTokens.size`, and the
   reduced-motion block's owner list (`:2180`, which already names `c4-4`).
7. `tokens.test.ts`'s **set equality** on the inventory and its `toHaveLength(65)` pin — moved
   deliberately or not at all.
8. `.stylelintrc.json` — the shadow, radius, spacing, duration and typography allowed-lists, the
   `outline: none` ban, and the two path-scoped overrides (`tokens.css`, `fonts.css`) which
   `lint-gates.test.ts` asserts are exactly two.
9. `no-scryfall-hosts.test.ts` — the host **family**, over every tracked file under `src/`.
10. `copy-rules.test.ts` — the file half (prose only in `COPY_MODULES`), the **attribute half**
    (every literal reaching nine read-aloud attributes, whatever its shape), and the `!`/emoji/
    "something went wrong" ban across all of `src/`.
11. `wire-contract.test.ts` — every `components.schemas` name and every `schema.ts` alias is banned
    outside `src/api/`; a locally-declared `interface CardTileProps { card: { name: string } }` is
    fine, a re-declared `CardSummary` is not.
12. `gate-geometry.test.ts` — no `.tsx` test under `tests/`, no test file outside the two roots,
    no `.jsx`/`.mjs`/`.cjs`.
13. `store-writes.test.ts` (AD-12's "nothing else writes the store") and
    `package-contract.test.ts`.
14. `AppShell.test.tsx`'s placeholder assertions (`:114-180`) — the shell's own placeholder must
    still fire when `left` is empty. Only `App.test.tsx`'s **displacement** assertion changes.
15. The **committed bundle + `plugin/` mirror** drift gates. `npm run build` mutates `src/`.

### Source tree — what exists, what this story touches

```
ui/src/
  <the new category>/  ← Q1. A component that holds state or takes a handler cannot live in
                         src/components/ — the coverage guard makes that a set equality and the
                         per-primitive bans make it a category. Decide the home, build its
                         coverage guard IN THIS COMMIT, and write the posture down.
                         NAMES: `CardTile` and `CardGrid`, matching DESIGN.md and UX-DR14/UX-DR4
                         rather than inventing `DeckGrid`/`TileGrid` — every artefact, every
                         guard comment and the mock's own component all say "card tile", and
                         c4-5/c4-6/c6-7 will search for that spelling. Directory-per-component,
                         three files, no barrels, flat kebab-case classes prefixed with the
                         component (`card-tile-caption`, never `card-tile__caption`)
  components/
    CardPlaceholder/   ← first CONSUMER, not an edit. All three variants get mounted for the
                         first time; the `Tile` exemplar in its .test.tsx is the mapping to copy
    Panel/             ← the grid's container (level default, overflow: hidden, 12px body padding)
    AppShell/          ← UNTOUCHED. Its `left` placeholder is DISPLACED by App.tsx, never deleted
    ManaCost/, Badge/  ← available; the quantity badge is NOT `Badge` (different material — scrim
                         + blur — and a different radius source; say which you used and why)
  state/
    deck.ts            ← READ ONLY. `surfaceOf`, `DeckBoards`
    deckGroups.ts      ← READ ONLY. `boardsOf`, `TYPE_GROUPS`, `CardGroup`
    cards.ts           ← READ ONLY. `useCardEntry`, `hydrateCard` — Q9 decides whether this story
                         is their production consumer or whether c4-5 is
  styles/
    card-geometry.css  ← READ ONLY. `.card-shape`, consumed by class name with no import
    tokens.css         ← EDITED, twice and deliberately: the ring token (Q2, AC 21) and the
                         reduced-motion scale fallback (AC 18). Both are the first of their kind
  api/
    client.ts          ← the path builders live here, but this story makes NO fetch. Whether an
                         image-URL builder belongs here is a judgement — say which way and why
  App.tsx              ← EDITED: the `left` slot finally gets a grid
ui/tests/              ← node project. The new category's coverage guard, the CARD_SHAPED entry,
                         the token pins, and the firing/silent pairs for each
```

**Backend: read-only.** Every route, token and contract this story renders already ships. Nothing
under `src/` changes except the built bundle.

### The inherited deferrals (AC 28 — give each a disposition)

Search `deferred-work.md` for `c4-4`. Summarised, with the line where each lives:

1. **The pacer queue can outlive the connection-pool timeout** (`:2617`, re-homed here at c4-1
   Q7). *"The story that will actually produce the burst this entry describes is **c4-4, the
   card-art grid** — the first surface that mounts ~99 `<img src="/api/card-image/…">` at once and
   therefore the first thing that can push the pacer queue past the pool timeout."* Read it before
   changing any pacer constant. Q7 is the lever.
2. **The image route reads the whole card row to get one URL** (`:2742`, re-homed here at c4-1
   Q7). *"**Home: c4-4** … the first story that issues these requests in bulk and therefore the
   first that could measure whether the whole-row read is worth a projection."*
3. **The backoff `502` answers with no `Retry-After` header** (`:3213`). Declined at c3-8's review
   *"so the tile author decides with the UI in view"*. **Home: c4-4**, beside the blind-spot row it
   would resolve. This story is the UI in view.
4. **The named placeholder's `overflow-wrap: anywhere` breaks long names mid-word, and the
   VERTICAL edge of the same trade is undeclared** (`:3623-3636`). *"c4-4 owns the grid and could
   revisit it with a real column width in hand."* Both halves — the mid-word break and the
   too-tall stack clipping at both edges with no clamp.
5. **A whole view of loading wells is total silence to assistive technology** (`:3638-3646`). Each
   well is correctly `aria-hidden` per tile, but during first paint a grid is *nothing but* wells.
   *"Whether the VIEW should carry a single polite live-region note during load is a composition
   question this story structurally cannot answer — it mounts nothing. **Home: c4-4**."* This
   story mounts it.
6. **Whether an element carrying `card-shape` is actually a CARD is not decidable from a
   stylesheet** (`:3587-3596`). *"**Home: review, at every card-shaped story; c4-4 is the first
   where the cross-file case becomes plausible.**"* Both directions: `.card-shape` on a non-card,
   and a card-shaped element given a chrome radius by a rule in a non-`CARD_SHAPED` file.
7. **Nothing checks that the RIGHT type role was chosen for the content** (`:3598`+, c4-3's probe
   (j), which PASSED). Not statically decidable; review's, at every story that renders an
   identifier — **or a card name** (Q3 is this entry's second instance).
8. **The first paint against a fully dead CDN takes ~124 s** (`:3131`). *"Severity: Low today …
   **Medium if c4-4's manual testing finds it.**"* Task 7 is that manual testing.
9. **The `images.py` split decision is parked at the C4 retrospective** (`:2989-2997`), *"by then
   c4-4 (the art grid) and c4-6 (the flip control) will have exercised all three mechanisms
   against real decks, which is the evidence the decision actually wants."* Disposition: feed the
   evidence forward; do not decide it here.
10. **c4-3's composition eye-check was re-homed here BY NAME** (`ui/README.md:1192` and the
    blind-spot row at `:1011`): *"What the harness could NOT answer is composition: a placeholder
    beside a real card face in a real grid is **c4-4's**, by name."* Task 7.
11. **A `ui/tests/` file may import an app module only if that module has no relative imports**
    (the measured `tsc -b` project-boundary rule). If this story's new guards read source as
    **text** — the idiom every other guard uses — it does not fire; say so, measured, with
    `npx tsc -b --force`.
12. **C3 retro action F1 — a gate banning story-key-shaped strings from rendered UI text**, owner
    *"Brad (c8-5, or earlier if a C4 story is nearer)"*. c4-2 declined it and counted six such
    strings on the real render, `c4-4` among them. **This story removes one of the six** (the left
    column's grid placeholder). Record the new count; the gate itself stays c8-5 unless argued
    otherwise.

### Open questions — answer these before writing code

**Q1 — Where does a component that holds state or takes a handler live, and what is its posture?**
*Proposed:* **a second list in `shell.test.ts` — `CONTAINERS` — with its own git-derived coverage
guard and its own written-down posture, and the components staying under `src/components/`.**
Rationale: the guard that makes this a question is a **set equality** over `src/components/`, so
the cheapest correct fix is to widen the covered set rather than move files out from under the
three guards that are path-scoped to it — and the three are **measured, not feared** (AC 2):
`shell.test.ts`'s coverage guard and posture bans, `posture.test.ts`'s cross-tree value-import
rule, and — the one that bites hardest here — `shell.test.ts`'s **`px`-literal DESIGN.md citation
check**, which is scoped by `startsWith('src/components/')` and is the gate that would otherwise
police this story's 176px grid minimum. (Everything else follows the file: both stylesheet scans
are `ls-files '*.css'` over the whole repo, `copy-rules` and `no-scryfall-hosts` scan all of
`src/`.) A second list says what a container MAY do (hold state, take handlers, hold a `ref`,
subscribe to the store, import from `src/state/`) and what it still may **not** (fetch — the door
stays `client.ts`; declare a token; write the store). *The alternative* — `src/views/` or
`src/deck/` — reads better and is what most codebases do, but it must then re-create those three
to avoid being a hole, and the story that discovers the hole is the one that finds a
`<div onClick>` in it.
**Whichever way, the new category's coverage guard ships in this commit** (AC 1), and `ui/README.md`
gains the paragraph the next fifteen component stories will read.

**Q2 — One ring token or two, and does the live ring ship with nothing to set it?**
*Proposed:* **ship `--shadow-focus-ring-over-art` only, and leave the live ring to c4-5.**
Rationale: `ui/README.md` already rules that a composite is a token (*"a live ring, a pinned
ring"* is its own example), so the mechanism is settled; what is open is scope. The focus ring is
reachable **in this story** — AC 20 makes tiles focusable — so it has a consumer and a test. The
live ring's only setter is the inspection target, which is c4-5's, and this repo's standing rule is
that *"an alias is added only in the commit that gives it a consumer"* (`ui/README.md`, and c3-2
declined `Card` on exactly that ground). *The alternative* — ship both, and move the pin once
instead of twice — is defensible and cheaper in diff, but it puts an unused token in a layer whose
inventory is pinned by set equality precisely so that additions are decisions. **Note the pin moves
in TWO files** (`tokens.test.ts`'s `expectedNames` + `toHaveLength`, and `token-usage.test.ts`'s
`declaredTokens.size`) — *"both move together or the pair is wrong."*

**Q3 — Does every card name in the grid render in CAPITALS?**
*Proposed:* **yes — ship the uppercase caption, and record the decision with its reason rather
than letting the gate make it silently.** Rationale: DESIGN.md:379 says `{typography.label}`, the
`label` role declares `textTransform: uppercase`, and `findRoleWithoutCompanions` derives the
requirement from the artefact itself — so the three artefacts agree and only the mock dissents, and
the mock is explicitly *"read for arrangement and density"* rather than for rules. A card name is
also a **chrome label** here, not retypeable data: unlike c4-3's truncated uuid, nothing breaks if
the reader copies `BLACK LOTUS` (browsers copy the untransformed source text anyway) and the
uppercase is what makes a 176px caption read as a label under a picture rather than as body text.
*The alternative* — `--type-body` at 14px, or a DESIGN.md amendment adding a non-uppercase caption
role — is a real option and it is where this goes if the eye-check (Task 7) says a grid of 99
shouting names is ugly. **This is c4-3's probe (j) generalised, and the honest framing is that no
gate can answer it: it is a product judgement, and it needs Brad's eye on a real screen.**

**Q4 — Does the tile announce its card name once or twice?**
*Proposed:* **`alt=""` on the `<img>`, with the caption carrying the name — and UX-DR48's grid-tile
clause corrected in the record rather than obeyed literally.** Rationale: UX-DR48's rule is not
arbitrary, it is *reasoned*: thumbnails in rows use `alt=""` *"because the name is announced once,
from the row text"*, and grid tiles keep the name *"because there the image is the only carrier."*
Measured against this component, **the second premise is false** — UX-DR14 puts the name in a
caption directly below the art, so the tile has exactly the structure the `alt=""` clause
describes. With the tile a `<button>` (AC 20), both strings land inside one accessible name and a
screen-reader user hears "Black Lotus Black Lotus". Applying the rule's own logic beats applying
its letter. *The alternative* — keep `alt={name}` and hide the caption from AT — inverts which
element is authoritative and makes the visible text the decoration, which is worse. **Record which
story's test proves it, and note that the named placeholder already exposes the name (c4-3 AC 13),
so the same question applies to the placeholder path and must get the same answer.**

**Q5 — Is the grid flat, or grouped by card type — and where do the commander and the sideboard
go?** *Proposed:* **flat, in `TYPE_GROUPS` order, with the commander rendered first and the
sideboard deferred to c4-7 by name.** Rationale: the composition reference shows one flat grid in
one `Panel`; the epic's own c4-4 acceptance criteria say nothing about group headers while c4-7's
say a great deal; and UX-DR12's group header is specified as *"the text-list unit"*'s divider.
Flattening `boards.mainboard` in order preserves the visual grouping (creatures cluster, then
instants, then lands) without inventing headers the story was not asked for, and it keeps
`GroupHeader`'s `<h2>` semantics for the panel that actually needs them. The commander is 16 of 40
real decks and filing it into "Creatures" *"misstates the deck to anyone reading the list"*
(`deckGroups.ts`'s own words); rendering it first, unlabelled, is the minimum honest treatment.
*The alternative* — a headed section per type group in the grid — is what EXPERIENCE.md's Flow 1
implies (*"the new card appears in its type group"*) and it may well be right; it is more work,
it collides with the mock, and it needs a ruling rather than a default. **Either way the sideboard
gets a named owner in this commit** — 41 rows across 5 decks silently vanishing is the
conservation failure `boardsOf` was written to make impossible.

**Q6 — What does the grid expose to assistive technology, given it has no group headers and no
live region?** *Proposed:* **the `Panel` title carries the counts** (the mock's *"Maindeck · 60
cards · 16 distinct"* shape, from `DeckDetail.mainboard_count` and `distinct_cards`, which both
already ship), **each `<li>` carries the card name once** (Q4), **and the quantity lives in the
badge with an accessible spelling on the tile rather than a separate label**. Rationale: UX-DR16
delegates the accessible quantity signal to *"the group-header count and the coalesced live-region
announcement"* and this story ships **neither** — so delegating without saying so would leave the
quantity announced as the bare string "×4" or not at all. *The alternative* — a visually-hidden
"4 copies" per tile — is authored copy and joins `COPY_MODULES` (the attribute half catches it
whatever its shape), which is fine but should be a decision. **Note the panel title is authored
copy too if it is assembled from words**, and `DeckBadges` is the precedent for how a
count-plus-word label is declared.

**Q7 — Do all ~99 `<img>` mount at once, or is loading deferred?**
*Proposed:* **mount them all, with `decoding="async"`, and NOT `loading="lazy"` — and record the
arithmetic either way.** Rationale: the deck grid is the app's primary surface and a 99-tile
Commander deck is roughly two to three screenfuls at 1720px, so lazy loading would defer maybe half
the tiles — while breaking the one thing the epic asks for, which is that *"layout renders
immediately … and layout never reflows on image arrival"* (a lazy `<img>` inside a fixed 63:88 box
does not reflow, so that half survives, but the scroll-triggered fill is a second loading pattern
the UX inventory never describes). The measured cost of not deferring is the cold paint the epic
already accepts as an expected observation: ~99 fetches, ~9.8 s, 8.5 MB, **once**, after which the
disk cache serves at ~10.3 ms/tile and the browser's own year-long `immutable` cache serves at
zero. *The alternative* — `loading="lazy"` — is one attribute and it is the only lever this story
has over the pacer-queue ledger entry (deferral 1), so if Task 7's eye-check finds the cold paint
genuinely unpleasant this is the knob. **Whichever way, the record carries the arithmetic**, because
the next person to ask will otherwise re-derive it.

**Q8 — Where does "the image has arrived" live, and is the well behind the `<img>` or beside it?**
*Proposed:* **per-tile `useState` driven by `onLoad`/`onError`, with the well as a sibling that the
loaded image replaces.** Rationale: there is no stateless spelling of this that is honest — a
CSS-only fade animates on mount rather than on arrival, and an `<img>` that has not loaded paints
nothing at all, so "silent well" and "faded-in art" are two different renders and something has to
know which. `onLoad` is the browser's only signal, and needing it is exactly the Q1 category
signal. *The alternative* — the well as a **background** on the same element the `<img>` sits in,
with only opacity changing — is fewer elements and one less state transition, but it makes the
error case awkward (a failed `<img>` must be removed, not faded) and it puts a
`--surface-well` background under a card face whose PNG corners are transparent, which DESIGN.md
explicitly cares about (*"png faces with transparent corners sit flush"*). **Note the state is
per-tile and must not be lifted**: 99 tiles sharing one loaded-set in the store is a store write
this story is not allowed to make (AD-12, `store-writes.test.ts`).

**Q9 — Is this story a consumer of `useCardEntry`/`hydrateCard` at all?**
*Proposed:* **no — the grid renders the board it was handed, and the cache stays c4-5's.**
Rationale: `DeckCardSummary.card` already carries name, cost and type line for every tile, and
`seedCardSummaries` has already put all of them in the cache; the tile needs nothing a `Card`
would add (oracle text and price are the **detail panel's**, and `image_uris` is not consulted
because the tile asks the image route directly). Measured, the unknown-card variant is unreachable
from a deck payload — **0 dangling references across 2,027 rows** — so the branch that would need a
cache read has no population. Hydration exists for hover, and hover is c4-5's. *The alternative* —
subscribe per tile so that a `deck_changed` in Epic 5 updates tiles individually — is real but
premature: the refetch design is UX-DR35's *"the current deck stays on screen"*, which is a
whole-payload replacement, not a per-tile one. **If the answer is "no", say it loudly**, because
`useCardEntry`'s docstring says a tile is its expected caller and the next reader will assume it.

**Q10 — What does this story render for a deck with zero cards, and for a card whose quantity is
zero or absent?** *Proposed:* **an empty `<ul>` and nothing else — the copy is c4-12's, and this
story must simply not crash or render an empty `Panel` with a stray header.** Rationale: c4-12 owns
the in-grid line (EXPERIENCE.md:70, verbatim copy under UX-DR33), so writing it here would fail
`copy-rules.test.ts` and pre-empt a story. But *"not this story's copy"* is not the same as *"not
this story's problem"*: `boardsOf([])` returns three empty boards, and a component that maps over
them without care renders a titled panel containing nothing, which is worse than either answer.
**And the totality lesson is measured, not belt-and-braces**: c4-2's review found `DeckBadges`
crashing the whole app on one absent prop — *"a presentation primitive that crashes the whole app
on one absent prop is the FR-13 posture inverted, and totality here costs one keyword."* Apply the
same `typeof`/`Number.isFinite` discipline to `quantity`, and use `filled()` rather than truthiness
where a slot is optional.

### References

- Epic story text: [epics-companion-app.md#Story 4.4](_bmad-output/planning-artifacts/epics-companion-app.md#L1941-L1991) · Epic 4 header [#L1837-L1843](_bmad-output/planning-artifacts/epics-companion-app.md#L1837-L1843) · c4-3 (what this story mounts) [#L1911-L1939](_bmad-output/planning-artifacts/epics-companion-app.md#L1911-L1939) · c4-5 (the inspection contract this story must not implement) [#L1993-L2034](_bmad-output/planning-artifacts/epics-companion-app.md#L1993-L2034) · c4-6 (the flip control, which owns the tile's top-left) [#L2035-L2083](_bmad-output/planning-artifacts/epics-companion-app.md#L2035-L2083)
- **The UX rules, verbatim**: **UX-DR14** (card tile) [#L402-L407](_bmad-output/planning-artifacts/epics-companion-app.md#L402-L407) · **UX-DR16** (quantity badge) [#L422-L424](_bmad-output/planning-artifacts/epics-companion-app.md#L422-L424) · **UX-DR4** (card geometry + the grid track) [#L351-L354](_bmad-output/planning-artifacts/epics-companion-app.md#L351-L354) · **UX-DR36** (placeholder-then-fill, no reflow) [#L541-L545](_bmad-output/planning-artifacts/epics-companion-app.md#L541-L545) · **UX-DR42** (the reduced-motion inventory) [#L577-L584](_bmad-output/planning-artifacts/epics-companion-app.md#L577-L584) · **UX-DR48** (alt text — and the clause Q4 questions) [#L611-L614](_bmad-output/planning-artifacts/epics-companion-app.md#L611-L614) · **UX-DR44** (ul/li, headings) [#L590-L595](_bmad-output/planning-artifacts/epics-companion-app.md#L590-L595) · **UX-DR47** (a real button, ≥24px) [#L607-L609](_bmad-output/planning-artifacts/epics-companion-app.md#L607-L609) · **UX-DR7** (art untinted; nothing imitative) [#L364-L368](_bmad-output/planning-artifacts/epics-companion-app.md#L364-L368) · **UX-DR3** (tabular numerals) [#L346-L349](_bmad-output/planning-artifacts/epics-companion-app.md#L346-L349) · **UX-DR5** (the spacing scale; the mock's one-offs are drift) [#L356-L357](_bmad-output/planning-artifacts/epics-companion-app.md#L356-L357) · **UX-DR8** (the two-column composition) [#L372-L378](_bmad-output/planning-artifacts/epics-companion-app.md#L372-L378)
- **The visual contract**: [DESIGN.md — Card tile](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L379) · Quantity badge [#L381](…/DESIGN.md#L381) · the `card-tile` frontmatter block (radius, aspect, shadow, live-ring, **focus-ring-over-art**, hover-scale, transition) [#L152-L159](…/DESIGN.md#L152-L159) · `quantity-badge` block [#L171-L176](…/DESIGN.md#L171-L176) · the `label` role and its `textTransform: uppercase` [#L66-L72](…/DESIGN.md#L66-L72) · card geometry, exact and exclusive, and the mock's five corrections [#L362](…/DESIGN.md#L362) · *"read the mock for arrangement, this file for rules"* [#L366](…/DESIGN.md#L366) · the grid track and the 1100→2560px envelope [#L344](…/DESIGN.md#L344) · elevation and the shadowless-theme argument [#L348-L356](…/DESIGN.md#L348-L356)
- **The behaviour contract**: [EXPERIENCE.md — Card tile row](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L83) · Quantity badge [#L85](…/EXPERIENCE.md#L85) · placeholder-then-fill [#L105](…/EXPERIENCE.md#L105) · the empty-deck line that is **c4-12's** [#L70](…/EXPERIENCE.md#L70) · reduced-motion inventory [#L152](…/EXPERIENCE.md#L152) · semantic structure (ul/li) [#L154](…/EXPERIENCE.md#L154) · alt text [#L157](…/EXPERIENCE.md#L157) · the latency contract and the 1 s warm render [#L160-L168](…/EXPERIENCE.md#L160-L168) · Flow 1's *"appears in its type group"* [#L190](…/EXPERIENCE.md#L190)
- **The composition reference** (arrangement only): [Planeswalker Companion.dc.html](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/imports/claude-design/Planeswalker%20Companion.dc.html) — the flat grid in one `Panel` titled *"Maindeck · 60 cards · 16 distinct"*, `gap:18px` (drift), the badge as a sibling `<span>` with `padding:2px 9px` (drift) · [the mock's `CardTile`](…/imports/claude-design/_ds/_ds_bundle.js#L199-L256) — a `<figure>`/`<figcaption>` at `--radius-md`, `width*1.4`, `object-fit: cover`, and a caption with the uppercase dropped
- **The seam this story consumes**: [card-geometry.css](ui/src/styles/card-geometry.css) · [CardPlaceholder.tsx](ui/src/components/CardPlaceholder/CardPlaceholder.tsx) · [the `Tile` exemplar](ui/src/components/CardPlaceholder/CardPlaceholder.test.tsx#L347-L440) · [deckGroups.ts — `boardsOf`, `TYPE_GROUPS`](ui/src/state/deckGroups.ts) · [deck.ts — `surfaceOf`](ui/src/state/deck.ts#L386-L428) · [cards.ts — `useCardEntry`](ui/src/state/cards.ts#L523-L538) · [App.tsx](ui/src/App.tsx#L102-L132) · [AppShell.tsx — the `left` slot](ui/src/components/AppShell/AppShell.tsx#L122-L130) · [Panel.css — `overflow: hidden`](ui/src/components/Panel/Panel.css#L31-L45) · [Footer.css — the shipped focus idiom](ui/src/components/Footer/Footer.css#L95-L111)
- **The gates that will fail first**: [shell.test.ts — the closed category](ui/tests/shell.test.ts#L1113-L1360) · the bare-`1fr` ban and the pre-blessed `minmax(176px, 1fr)` [#L335-L410](ui/tests/shell.test.ts#L335-L410) · the `px`-literal citation check [#L960-L1000](ui/tests/shell.test.ts#L960-L1000) · [token-usage.test.ts — `CARD_SHAPED`](ui/tests/token-usage.test.ts#L750-L870) · `findRoleWithoutCompanions` [#L443-L560](ui/tests/token-usage.test.ts#L443-L560) · the reduced-motion block's owner list [#L2140-L2184](ui/tests/token-usage.test.ts#L2140-L2184) · [tokens.test.ts — the 65-token set equality](ui/tests/tokens.test.ts#L216-L274) and the elevation assertions [#L384-L393](ui/tests/tokens.test.ts#L384-L393) · [posture.test.ts](ui/tests/posture.test.ts#L188-L341) · [no-scryfall-hosts.test.ts](ui/tests/no-scryfall-hosts.test.ts) · [copy-rules.test.ts — `COPY_MODULES`](ui/tests/copy-rules.test.ts#L96-L140) · [gate-geometry.test.ts](ui/tests/gate-geometry.test.ts) · [.stylelintrc.json](ui/.stylelintrc.json) · [eslint.config.js — the a11y rules](ui/eslint.config.js#L56-L110)
- **The token layer**: [tokens.css — the reduced-motion registration point](ui/src/styles/tokens.css#L199-L242) · motion and elevation [#L180-L197](ui/src/styles/tokens.css#L180-L197) · the focus-ring trio [#L113-L118](ui/src/styles/tokens.css#L113-L118) · typography and its tracking companions [#L135-L152](ui/src/styles/tokens.css#L135-L152)
- **The backend this story finally exercises**: [cards.py — `read_card_image`](src/companion/app/routes/cards.py#L223-L300) · the binary-200 declaration and *"the generated TypeScript lies to c4-4"* [#L161-L180](src/companion/app/routes/cards.py#L161-L180) · [images.py — `ImageSize`, `DEFAULT_IMAGE_SIZE`, `IMAGE_CACHE_CONTROL`](src/companion/app/images.py#L132-L175) · the pacer and the negative cache [#L340-L360](src/companion/app/images.py#L340-L360)
- **The previous stories**: [c4-3](_bmad-output/implementation-artifacts/c4-3-card-placeholders-named-unknown-and-loading-wells.md) — its Q2 (the shared class), Q8 (the discriminated union) and probe (j) · [c4-2](_bmad-output/implementation-artifacts/c4-2-deck-state-bootstrap-and-the-type-grouped-decklist.md) — the derivation and the `DeckBadges` totality lesson · [c4-1](_bmad-output/implementation-artifacts/c4-1-a-single-card-hydration-cache-with-in-flight-deduping.md)
- **The ledger**: [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — search `c4-4` (entries at `:2617`, `:2742`, `:2995`, `:3131`, `:3213`, `:3396`, `:3594`, `:3628`, `:3644`)
- Project rules: [project-context.md](_bmad-output/project-context.md) · frontend conventions [ui/README.md](ui/README.md) — especially *"The card shape"* (`:740`), *"The presentation-only primitives"* (`:474`), the token-layer bans (`:189`) and the **blind-spot table** (`:985`), four of whose rows were written for this story

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow.

### Debug Log References

- Baseline, measured on this machine at `b47f603` and matching the story's table exactly:
  **1,024 frontend / 42 files** (4.6 s), **2,447 Python passed / 1 skipped / 54 deselected**
  (120 s); lint, `format:check`, `npx tsc -b --force`, `ruff check`, `ruff format --check`,
  `mypy src/`, `mypy src/ --platform win32` all green. No `Worker exited unexpectedly` occurred at
  any point in this story.
- **Every number in §"What the real data says" was re-measured read-only against
  `%LOCALAPPDATA%\artificial-planeswalker\cards.db` and every one held**: 40 decks, 2,027
  `deck_cards` rows, 1,061 distinct ids; largest deck **99 distinct / quantity sum 100**;
  **395 of 2,027** rows with quantity > 1 but **1 of 99** in that deck; max quantity **34**
  (`Swamp`), then 32/31/27/25, all basics; longest name in that deck **42**
  (`Barkchannel Pathway // Tidechannel Pathway`), median 16, shortest 5, **13 of 99** over 24
  characters; **0** deck-referenced cards with no `image_uris`; 16 of 40 decks with a commander,
  5 with a sideboard (41 rows). Nothing in the ACs had to move.
- Live measurement, backend on `127.0.0.1:8765` with the 99-card deck active: a fully warm paint
  is **99 requests in 0.55 s = 5.6 ms/tile**, and the deck is **8.47 MB** — the epic's 8.5 MB
  confirmed to two significant figures, and the ~10.3 ms/tile warm figure beaten on this machine.
- Screenshots (scratchpad, not committed): the real app at 1720px cold and warm, and a
  state harness serving the BUILT stylesheet against hand-written markup — the instrument c4-3
  and c4-2 both used.
- **THE COLD PAINT, OBSERVED FOR REAL at review 2026-08-04** (Decision 1 — the story's first
  record ticked the Task 7 subtask without having done it; ruled "perform it now"). Disk cache
  moved aside, `Atraxa Counter Cabinet v2 (owned)` (99 distinct) active, real browser, live CDN.
  **Backend fetch window: 9.3 s for all 99 images** (cache-file mtimes, first→last — the pacer's
  0.1 s turnstile binding within 5% of the modelled 9.8 s). **Perceived paint: 2–3 s** (Brad's
  observation, fast fibre): the browser prioritises in-viewport images, so the visible screenful
  fills in seconds while the rest of the deck completes off-screen. No spinner, no broken glyph,
  nothing stuck. The ~10 s figure is confirmed AND largely invisible — the two claims were
  conflated in every earlier record and are different numbers. The dead-CDN ~124 s case remains
  unobserved (the CDN was alive); it stays with c10-3.
- **AC 31 hashes, recorded at review 2026-08-04** (the story's first record carried sizes only).
  Baseline (`git show HEAD:…` at `b47f603`): `index-CdikAaRP.js`
  `49a35b61…39425fd2e4`, `index-DGjO7yGD.css` `09063845…1643258228`, `index.html`
  `79c37500…23740e9fb6`, `space-grotesk…woff2` `06408904…37ab1ce9d` (unchanged across the
  story), `favicon.svg` `9be16ea2…85d1fbd0` (unchanged). After the review-patch rebuild:
  `index-mnVGJAvJ.js` `d5298cc7…c22f77a5ae` (**208,004 bytes** — the pre-review patch build was
  `index-DdSC6ddi.js` at 207,941; the settle-both-halves and cardId-reset patches grew it 63
  bytes), `index-Cgivw4Tq.css` `679d20b6…92dc82f60` (11,579 bytes, unchanged by review),
  `index.html` `07c5670d…9f63fbf3a`. The `plugin/` mirror is byte-identical file-for-file
  (verified by sha256 diff).

### Completion Notes List

**All ten open questions answered; nine as proposed, ONE against the proposal with a measurement.**

- **Q1 — RULED AGAINST THE PROPOSAL: a new `src/containers/` tree, not a `CONTAINERS` list inside
  `src/components/`.** The proposal's premise was that only two `posture.test.ts` rules are
  path-scoped to that directory. Measured, there are **three** `it.each(componentSources)` blocks
  — the cross-tree value-import ban (`:197`), the type-only `react` import (`:208`) **and the
  behaviour-family ban (`:262`)** — and a container must be exempt from all three. The decisive
  finding is not the count but what an exemption would blind: the cross-tree rule filters on
  `!target.startsWith('src/components/')`, so a container living inside that tree would have made
  **a presentation-only primitive importing a stateful container invisible to every guard in the
  repo**. Outside it, the rule that was already green catches it for free — a firing proof is now
  in `posture.test.ts`. Cost: exactly one guard had to be **widened** (the `px`-literal DESIGN.md
  citation check now scopes to a list of roots) rather than weakened, and `src/components/` stays
  literally total with no exempted member. AC 2's measurement is recorded in `ui/README.md`.
- **Q2 — as proposed.** `--shadow-focus-ring-over-art` only; `live-ring` is c4-5's and its absence
  is *asserted*, so the story that adds it is told the pin moves with it. Inventory 65 → **66**,
  both pins moved together, value asserted against DESIGN.md's `components.card-tile`.
- **Q3 — as proposed, and confirmed by eye.** The caption ships in CAPITALS. Checked on a real
  screen at 1720px with 99 real names: it reads as a label belonging to the picture, not as
  shouting. The uppercase is CSS, so the DOM text, the accessible name and the clipboard are
  untouched — asserted.
- **Q4 — as proposed.** `alt=""`; the caption is the name, once.
- **Q5 — as proposed.** Flat, `TYPE_GROUPS` order, commander first and unlabelled; the sideboard
  is not in the art grid and **c4-7** is named as its owner, in the component and in a test.
- **Q6 — as proposed in substance, refined in mechanism.** Untitled `Panel` (the `h1` and
  `DeckBadges` already carry the counts; an untitled panel invents no name). The quantity is
  announced with the card because the badge's id joins `aria-labelledby` — no authored string, so
  no COPY_MODULES entry is owed.
- **Q7 — as proposed.** All ~99 mount at once with `decoding="async"`; no `loading="lazy"`, no
  `fetchPriority`. Both are asserted as rendered ATTRIBUTES, so a React 19 casing slip is a red
  test rather than a silent no-op.
- **Q8 — as proposed.** Per-tile `useState`, well as a sibling, never lifted.
- **Q9 — NO, said loudly.** Nothing here subscribes to `useCardEntry` or calls `hydrateCard`; the
  grid renders the board it was handed. Written at the top of `CardGrid.tsx` because
  `useCardEntry`'s own docstring names a tile as its expected caller.
- **Q10 — as proposed.** An empty `<ul>` in an untitled panel: a place for c4-12's copy, not a
  state pretending to be one. Asserted, including that the render contains no text at all.

**THE EYE-CHECK FOUND A REAL DEFECT, AND IT IS THE MOST VALUABLE LINE IN THIS RECORD.** The first
draft made the `<button>` a wrapper around the art and the caption, with the composite ring on an
inner card-shaped frame. Rendered in Edge with a REAL keyboard focus, that shows **two indicators
at once**: the composite hugging the card's rounded corners, and the browser's own focus ring as a
sharp-cornered rectangle around card-plus-caption. `outline: none` is banned in every spelling
(UX-DR46; stylelint bans all four) so the UA ring cannot be deleted — only replaced, and an
authored outline is the right shape only if the focused element is the card. Two repairs, applied
together and re-verified on screen: **the button now carries `card-shape`** (the caption is a
sibling naming it through `aria-labelledby`, which needs `useId` — a fourth independent reason
this cannot be a listed primitive), and **the outline is given the composite's own inner band**
(`--focus-ring-width` / `--focus-ring` at offset 0) so the two mechanisms occupy the same pixels
instead of stacking. One ring, DESIGN.md's exact geometry, over a light face and a dark one.

**A second defect was found by writing the tests, before any browser ran:** on the `onError` path
the tile would have shown the card's name TWICE — once inside c4-3's named placeholder, once in
the caption beneath it — and announced it twice inside one control. The caption is now suppressed
whenever the placeholder is naming the card, and that is asserted in both directions.

**Three green guards fired on correct code, and each repair is in the open:**
1. `copy-rules.test.ts` collected `alt=""` — the WCAG-required spelling for a decorative image —
   and demanded that a component owning **no words at all** join `COPY_MODULES`. Repaired with one
   condition that makes the attribute branch consistent with its sibling (which has excluded `''`
   since the guard was written), plus a firing/silent pair proving the narrowing is a narrowing.
2. `jsx-a11y`'s two UX-DR47 rules default to a handler list containing `onError` and `onLoad`,
   which are **resource-lifecycle events, not interactions** — no user in the causal chain, no
   keyboard equivalent to add, no role to promote. The list is narrowed to the six interaction
   handlers **in `eslint.config.js`, argued in the open**, the clean fixture now carries an
   `<img onLoad onError>` so the narrowing is exercised rather than described, and
   `lint-gates.test.ts` pins the resolved config against drift.
3. `no-descending-specificity` rejected hovering the grid ITEM while focusing the BUTTON — and it
   was right: the higher-specificity hover rule would have stripped the ring off a tile that was
   hovered *and* focused. Both states now sit on `.card-tile` at equal specificity, so the later
   rule wins by order.

**A REAL HOLE WAS FOUND IN THIS EPIC'S OWN DOCTRINE, by probe (e).** `tokens.css`'s reduced-motion
block instructs later stories that a motion a duration cannot switch off *"adds its own
declaration HERE"* — and **nothing checked it**. Deleting the scale fallback left the entire suite
green. A **derived** guard now fails any shipped block that declares a `transform` whose selector
is not neutralised in that block; it is not a list, so c4-6's 3D flip and c6-5's bloom are covered
the day they are written, and it carries a non-vacuity anchor because a tree with no transforms
would otherwise satisfy it by having no subject. The override needs `!important`, measured: the
two rules have identical specificity and `tokens.css` is imported first, so without it the block
would have parsed cleanly and done nothing.

**TEN EVASION PROBES, TEN CAUGHT, none passed.** (a) an unlisted module in the new tree → the
containers coverage guard; (b) `--radius-md` in the card-shaped stylesheet → CARD_SHAPED's second
half; (c) a local `aspect-ratio` → c4-3's one-declaration guard; (d) the caption's
`text-transform` deleted with its tracking left → `findRoleWithoutCompanions`; (e) the scale left
un-neutralised → **the new guard, which exists because this probe first PASSED**; (f) a literal
`240ms` → stylelint; (g) an `<img>` pointed at `cards.scryfall.io` → `no-scryfall-hosts`;
(h) `×` swapped for the letter `x` → this story's codepoint pin; (i) a bare `1fr` track →
`findContentFlooredTrack`; (j) a shadow token added without moving the sibling pin →
`declaredTokens.size`. Every probe ran through the **full** `npm test`, never a single file.

**Declared limits, so that nothing reads as coverage it does not have.** The geometry is not a
pixel in jsdom (`getComputedStyle().aspectRatio` returns `''` and would pass for the wrong
reason); no stylesheet is applied, so the shadow, ring, uppercase, blur and pop are source claims
only; the warm-cache `onLoad` race is **inert** in jsdom in both directions, so the suite can only
prove the guard does not fire wrongly; the accessible name's exact spelling cannot be read (jsdom
concatenates naming elements with no separator, so tests assert membership); and the ~10 s cold
paint, the pacer and the 300 s negative cache are backend behaviour this story never invokes.
Each has a named home in `ui/README.md`'s blind-spot table or the epic checklist.

**One finding recorded rather than fixed** (AC 25): `CardPlaceholder` renders a `<div>` and
`<button>`'s content model is phrasing content, so mounting the placeholder inside the tile is
invalid HTML by the letter of the spec. Every engine renders it, React does not warn, and the
accessible name computes normally; every alternative was worse. Argued and ledgered, home **c4-5**.

**Boundaries held.** `AppShell.tsx`, `CardPlaceholder`, `states.ts`, `cards.ts`, `deck.ts`,
`deckGroups.ts` and all seventeen primitives are untouched as source. No new dependency, no second
state library, no image-fetching code, no inline `style`. `posture.test.ts`'s one-door list still
reads `['src/api/client.ts']` **with no edit**, in the first story that puts remote images on the
screen. Python is untouched: **2,501 passed / 1 skipped**, the same suite as the baseline's
2,447 + 54 deselected.

**Counts.** Frontend **1,024 → 1,083** (42 → 44 files). Tokens **65 → 66**. Primitives 17,
unchanged; containers **3**, new. The **JS bundle finally grew** — 202,846 → **207,941** bytes —
which is AC 31's prediction confirmed: c4-3's was byte-identical because nothing imported
`CardPlaceholder`, and this commit imports it. CSS 6,187 → **11,579** bytes, its first growth
since c4-2. The `plugin/` mirror is byte-identical to the bundle, file for file.

### File List

**New**

- `ui/src/containers/CardTile/CardTile.tsx`
- `ui/src/containers/CardTile/CardTile.test.tsx`
- `ui/src/containers/CardTile/CardTile.css`
- `ui/src/containers/CardTile/QuantityBadge.css`
- `ui/src/containers/CardTile/imageUrl.ts`
- `ui/src/containers/CardGrid/CardGrid.tsx`
- `ui/src/containers/CardGrid/CardGrid.test.tsx`
- `ui/src/containers/CardGrid/CardGrid.css`

**Modified**

- `ui/src/App.tsx` — the `left` slot renders `CardGrid`; the displacement paragraph rewritten
- `ui/src/App.test.tsx` — the displacement assertion inverted; a new deck-on-the-glass test
- `ui/src/styles/tokens.css` — `--shadow-focus-ring-over-art`; the reduced-motion block's first
  registration
- `ui/tests/shell.test.ts` — the `CONTAINERS` category, its coverage guard and posture; the
  primitives' totality assertion; the `px`-literal citation check widened to a list of roots
- `ui/tests/tokens.test.ts` — inventory 65 → 66; `components.card-tile` typed; the ring's value
  and the live ring's deliberate absence
- `ui/tests/token-usage.test.ts` — `declaredTokens.size` 65 → 66; `CardTile.css` joins
  `CARD_SHAPED`; the derived transform-neutralisation guard and its firing/silent pair
- `ui/tests/posture.test.ts` — a firing proof that a primitive importing a container is caught
- `ui/tests/copy-rules.test.ts` — an empty user-facing attribute is not copy, with both halves
- `ui/tests/lint-gates.test.ts` — the a11y handler list pinned against drift
- `ui/tests/fixtures/a11y/clean.tsx` — an `<img onLoad onError>` exercising the narrowing
- `ui/eslint.config.js` — the two UX-DR47 rules take an explicit interaction-handler list
- `ui/README.md` — the containers category, motion and its registration point, the focus ring, the
  card-shape consumer note, the left-column displacement, `Panel`'s first consumer, three new
  blind-spot rows and the four c4-4 rows' dispositions
- `_bmad-output/implementation-artifacts/deferred-work.md` — twelve dispositions and five new
  residues
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status and narrative
- `src/companion/app/static/index.html`, `src/companion/app/static/assets/*` — rebuilt bundle
- `plugin/server/src/companion/app/static/**` — regenerated mirror

### Change Log

| Date | Version | Description |
| --- | --- | --- |
| 2026-08-04 | 0.3 | **REVIEWED → done.** Three-layer review (Blind Hunter / Edge Case Hunter / Acceptance Auditor): 28 raw findings → 2 decisions + 19 patches + 3 dismissed (container `.setState`/`fetch` regex weaknesses already double-covered by `store-writes.test.ts` and `posture.test.ts` repo-wide; untracked `graphify-out/`). **All 21 applied.** The two that mattered: (1) **the transform-neutralisation guard — this story's headline contribution — had a false-PASS path in the exact spelling its own cascade analysis proves inert** (`declarationsIn` strips `!important`, so a no-`!important` registration counted) and was blind to the individual `scale:`/`rotate:`/`translate:` properties; hardened to per-property `none !important` matching with firing probes for both holes. (2) **`settleIfCached` mitigated only the SUCCESS half of the warm-cache race its own header describes** — a negative-cached instant failure landing before React attaches `onError` left the tile on the silent well forever; the failed arm now settles too. Also: the art-state verdict now RESETS on a `cardId` change (render-time adjustment, race-free); the vacuous re-arm test re-renders for real; the wire-token boundary is asserted at the TYPE; probe (a)'s firing half feeds the actual coverage comparison; AC 12 gained its missing POSITIVE assertions (blessed track + token gap); the copy-rules `''` exemption narrowed to `alt` per ruling (an empty `aria-label` is collected again — flagged, not blessed); the container guard's comment stripper became string-aware, its roots check normalises traversals, and its `.test.ts` exemption verifies vitest; App.test asserts the img COUNT before the origin loop; CardGrid's conservation derives from the boards instead of restating the fixture. **A recorded "measurement" was found FALSE by measuring**: jsdom's accname is `Black Lotus ×4` — ID order, WITH a space — not the recorded run-together `×4Black Lotus`; the Q6 test now pins the exact spelling and the blind-spot row narrows to real-screen-reader phrasing. **Decision 1 executed: the cold paint was finally OBSERVED** — backend window 9.3 s for 99 CDN fetches (pacer model confirmed within 5%), perceived paint 2–3 s (viewport-prioritised); the two numbers were conflated in every earlier record and are different numbers. AC 31's hashes recorded (baseline + rebuilt; mirror sha256-verified identical). Frontend **1,083 → 1,086** (44 files), bundle 207,941 → **208,004** bytes, CSS unchanged at 11,579; Python re-verified clean after a DB-contention flake (server boot during suite) passed in isolation and on the clean re-run. All ten gates green. |
| 2026-08-04 | 0.2 | **IMPLEMENTED → review.** The deck is on the glass. **Q1 ruled AGAINST its proposal, with a measurement**: `posture.test.ts` has THREE `it.each(componentSources)` blocks rather than two, and its cross-tree rule filters on `!target.startsWith('src/components/')` — so containers kept inside that directory would have made *a primitive importing a stateful container invisible to every guard in the repo*. They live in **`src/containers/`** instead, with a git-derived coverage guard and a written posture; `src/components/` stays literally total, one guard was **widened** (the `px`-literal DESIGN.md citation check) rather than weakened, and the primitive→container import is caught for free by a rule that was already green. Nine other questions as proposed. **THE EYE-CHECK FOUND THE HEADLINE DEFECT**: with the button wrapping art *and* caption, a real keyboard focus renders TWO indicators — the composite ring on the card and the browser's own sharp-cornered ring around card-plus-caption — and `outline: none` is banned in every spelling, so the UA ring can only be REPLACED. Repaired by making the **button itself the card** (caption a sibling named through `aria-labelledby`, which needs `useId` — a fourth reason this cannot be a primitive) and giving the **outline the composite's own inner band**, so the two mechanisms occupy the same pixels; re-verified on screen over a light face and a dark one. A second defect was caught by the tests before any browser ran: the failed path would have shown and announced the card's name twice. **A REAL HOLE IN THE EPIC'S OWN DOCTRINE**, found by probe (e): `tokens.css`'s registration-point instruction had NO GATE — deleting the scale fallback left the whole suite green — so a **derived** guard now fails any shipped `transform` whose selector is not neutralised in that block (c4-6 and c6-5 are covered before they are written), with `!important` measured as necessary rather than assumed. **Three green guards fired on correct code and each repair is in the open**: `copy-rules` treated `alt=""` as copy (narrowed, with both halves proven); `jsx-a11y`'s UX-DR47 rules ban `onLoad`/`onError` by default, which are resource-lifecycle events rather than interactions (handler list narrowed in `eslint.config.js`, the clean fixture now exercises it, the resolved config pinned); and `no-descending-specificity` correctly rejected a hover rule that would have stripped the ring off a hovered-and-focused tile. **TEN PROBES, TEN CAUGHT.** Measured live against the running backend with the 99-card deck: **8.47 MB** (the epic's 8.5 MB confirmed) and a warm paint of **99 requests in 0.55 s = 5.6 ms/tile**. Every number in §"What the real data says" re-verified read-only and unchanged. Twelve inherited deferrals dispositioned (1 resolved structurally, 1 closed, 1 done, 3 re-homed by name, 3 not-triggered, 3 evidence-forward), five new residues declared including the argued `<div>`-in-`<button>` finding homed on c4-5. **1,024 → 1,083 frontend / 42 → 44 files**; tokens 65 → 66; Python **2,501 passed / 1 skipped**, unchanged. **The JS bundle finally grew** — 202,846 → 207,941 bytes, AC 31's prediction confirmed — CSS 6,187 → 11,579, mirror byte-identical. All ten gates green. |
| 2026-08-04 | 0.1 | **CONTEXTED off `b47f603`** on `feat/companion-c4`. Four categories open at once and each is a decide-once ruling ten-plus stories inherit. **(1) `src/components/` is a CLOSED category and the tile cannot join it** — `shell.test.ts:1257` is a git-derived SET EQUALITY over that directory and every member is banned from hooks, `on*` in either position, `ref`, spread and a value `react` import; a tile needs `<img onLoad>`, so a new module there is red listed AND unlisted. c4-4 decides where a stateful component lives (Q1). **(2) This story ships the FIRST motion in the codebase** — measured: zero `transition`, zero `animation`, zero `transform` across every tracked `ui/src` stylesheet, six of which say *"NO MOTION, DELIBERATELY"* and one of which names this story — and it is the first extension of `tokens.css`'s reduced-motion registration block, which `token-usage.test.ts:2172` already asserts names `c4-4` twice. A zeroed duration does not neutralise `scale(1.06)`; it only makes it instant. **(3) The focus ring is a composite stylelint forbids inline and the 65-token inventory does not carry** — the `box-shadow` allowed-list is `none` or `var(--shadow-*)`/`var(--glow)` and nothing else, and DESIGN.md files the value under `components.card-tile` rather than `components.elevation`; `ui/README.md` has already ruled the answer (*"a live ring, a pinned ring → add a token to the layer"*), so the pin moves in TWO files together (Q2). **(4) Every card name renders in CAPITALS by gate** — DESIGN.md puts the caption in `{typography.label}`, the label role declares `textTransform: uppercase`, and `findRoleWithoutCompanions` derives a hard requirement from exactly those two facts; the composition mock drops the uppercase and overrides the tracking, so the mock cannot ship. That is c4-3's probe (j) in its second instance (Q3). Also found: **the tile announces its card name twice** — UX-DR48 keeps `alt={name}` on grid tiles *"because there the image is the only carrier"*, which is measurably false for a component UX-DR14 gives a caption (Q4); **an `<img>` error event carries no wire token**, so the named placeholder in the grid is reached from `onError`, not from `entry.placeholder`; and **a cached image can finish loading before React attaches `onLoad`** — which is the NORMAL path here, because a successful image ships `max-age=31536000, immutable`, so the tile's happy case is the one jsdom can never see. Measured on the live DB: **99 tiles** in the largest deck, **1,061** distinct ids across 40 decks, **0** of them with no image data anywhere, **27** with per-face images (c4-6's control), **395 of 2,027** rows with quantity > 1 but only **1 of 99** in the largest deck, max quantity **34**, and **13 of 99** names over 24 characters so the caption ellipsis is a real path. 32 ACs, 10 open questions, 12 inherited deferrals (four of them `ui/README.md` blind-spot rows written for this story by name), 15 named don't-breaks. Baseline **1,024 frontend / 42 files** (measured), 2,447 Python. |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

2026-08-04: CODE-REVIEWED -> done. Three-layer review: 28 raw findings -> 2 decisions + 19 patches + 3 dismissed, ALL APPLIED. Headliners: the story's own transform-neutralisation guard had a false-PASS in the exact no-!important spelling its cascade analysis proves inert (and was blind to scale:/rotate:/translate:) — hardened per-property; settleIfCached settled a cached SUCCESS but not a cached FAILURE — both arms now settle; a recorded jsdom accname "measurement" was false by measuring (Black Lotus ×4, ID order WITH a space — now pinned exactly); the cold paint was finally OBSERVED (backend window 9.3 s / perceived 2-3 s — different numbers, both real). 1,083 -> 1,086 frontend / 44 files, bundle 207,941 -> 208,004 B, mirror sha256-identical. Ten gates green. Next: PR into feat/companion-c4

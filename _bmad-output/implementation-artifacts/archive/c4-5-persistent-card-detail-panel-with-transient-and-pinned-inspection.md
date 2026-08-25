---
epic: c4
story: c4-5
work_branch: feat/companion-c4
story_branch: feat/companion-c4-5-card-detail-panel
depends_on: >-
  c4-4 (merged at `b26e8f4`, PR #43) — `src/containers/` is the category this story lands in, and
  `CardTile` ships a real `<button>` with **no handler at all** specifically so this story adds one
  rather than reshaping the component. c4-3 (merged at `b47f603`) — `.card-shape` is the geometry
  the detail art consumes BY CLASS NAME, and `CardPlaceholder` is the component this story mounts a
  second time, at detail size. c4-2 (merged at `2a64231`) — `boardsOf` / `DeckBoards` supply the
  cold-open target, and `seedCardSummaries` is what makes "no spinner" mechanically true for
  single-faced cards. c4-1 (merged at `2095050`) — `useCardEntry` and `hydrateCard`; this story is
  the production consumer both were written for (`cards.ts:527` names "a hover handler, a detail
  panel opening" as the caller). Also **c2-7** (`Panel`, whose titled `level="overlay"` variant this
  story is the first to render and is homed to eye-check), **c2-6** (`AppShell`, whose right-column
  placeholder this story displaces), **c2-4** (the token layer, 66 tokens, both pins), **c3-2**
  (`GET /api/cards/{card_id}`, the hydration route) and **c3-5** (`GET /api/card-image/...`, which
  this story is the first to call at a non-default `size`).
baseline_commit: b26e8f4
---

# Story C4.5: Persistent card detail panel with transient and pinned inspection

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad reading through my deck,
I want the full card I'm pointing at to appear in a panel that's always there,
so that reading the whole deck is one continuous motion with no clicks.

**What this story really is.** Four stories built a deck view that cannot be interacted with. This
is the story that makes it respond. It is the **first user-interaction state in the codebase** —
every store write to date has come from a REST response or a poll tick, and the architecture spine
says in as many words that the SPA's *"state comes from exactly two inputs — REST responses and
WebSocket messages. Nothing else may write the store."* A hovered card is a third kind of input, and
this story has to narrow that sentence deliberately rather than quietly violate it (Q5).

It is also the story that **discovers what the two-tier cache is actually for**. The received
picture — from `EXPERIENCE.md:86`, and repeated in four modules' docstrings — is that name and cost
come free from the deck payload and *"the rest fills in place"* from `GET /api/cards/{card_id}`.
Measured against the shipped database, that picture is **wrong for single-faced cards and exactly
right for multi-faced ones**, and the difference is total, not statistical: `CardSummary` already
carries every text field the panel draws, so a single-faced card needs no request at all — while
**all 3,225 cards carrying `card_faces` have a blank top-level `oracle_text`, 100% of them**, so a
double-faced card's type line and rules text exist *only* behind hydration. Six of the 99 cards in
the largest real deck are in that second population. "The rest fills in place" is real; it just
fills in place for 6% of the deck rather than all of it (Q1).

Three more things open here:

1. **The design contract has a hole and a defect, both in this component.** The unpin control is
   *required* by UX-DR20 and specified nowhere — no size, glyph, position, label or token (Q3). And
   `components.card-detail.pinned-ring` is declared as `0 0 0 1px {colors.accent-dim}` on a
   `{colors.surface-overlay}` background, which is **2.70:1** — the pairing `DESIGN.md:305` bans by
   name and `token-usage.test.ts` gates. This is the identical defect the UX validation gate closed
   as **M4/C3** for `card-tile.live-ring`, and the fix was never carried across to the pinned ring
   (Q2).

2. **This story owes two composite tokens, and one of them has its absence asserted.**
   `tokens.test.ts:433` ships a test named *"does NOT ship the live ring, because nothing sets
   `live` until c4-5"*. Adding `--shadow-live-ring` turns that test red on purpose — it is the
   mechanism telling this story's author that the pin moves with it. The pinned ring is a second
   composite. **66 → 68, in two files, in the same commit** (Q4).

3. **The suite has no instrument for hover.** There is no `userEvent` anywhere in `ui/`, no
   `fireEvent.mouseOver`, and `@testing-library/user-event` is not a dependency —
   `tests/package-contract.test.ts` pins the dependency list, so adding one is a decision with a
   diff (Q9).

## Dev Notes

### The seam that already exists (do not rebuild any of it)

Four stories left this one a hole shaped exactly like itself. Everything below is **shipped and
green at `b26e8f4`**. Read it before writing anything.

**`CardTile` ships a handler-less button, on purpose.**
`src/containers/CardTile/CardTile.tsx:89-95`:

> **WHAT THIS TILE DELIBERATELY DOES NOT DO** — No inspection, no pin, no hover→detail wiring: the
> `<button>` ships with **no handler at all**, so **c4-5** adds one rather than reshaping the
> component.

Its markup is `<button type="button" className="card-shape card-tile" aria-labelledby={labelledBy}>`
and `CardTileProps` is five primitive values — `cardId`, `name?`, `cost?`, `typeLine?`, `quantity?`.
No `live`, no callbacks, no store subscription.

**The card cache is a plain function plus a pure selector, and the split is load-bearing.**
`src/state/cards.ts:43-55` rejects a `useCard(id)` that fetches, because *"N mounted tiles becoming
N request owners"* is the mistake `useSystemState` already taught. So:

- `useCardEntry(cardId): CardEntry | undefined` — **starts nothing**. Safe to call on every frame of
  a cursor sweep; the cost is a store read.
- `hydrateCard(cardId, read?): Promise<CardEntry>` — **owns the request**, callable from an event
  handler. Dedupes in-flight by shared promise, releases on every outcome, never rejects, caps at
  `MAX_ATTEMPTS_PER_CARD = 3`, and refuses `cardId === ''` terminally with zero requests.

`cards.ts:527` names this story as the caller: *"Whoever decides that a full record is actually
needed — a hover handler, a detail panel opening — calls `hydrateCard`."*

`CardEntry` is a discriminated union and **`undefined` means only "never seen"**:

```ts
| { status: 'summary';  summary: CardSummary }
| { status: 'loading';  summary: CardSummary | null }
| { status: 'hydrated'; card: Card }
| { status: 'unknown';  reason: ErrorReason | null; placeholder: PlaceholderKey | null
                      ; summary: CardSummary | null; retryable: boolean }
```

Every deck card is already seeded to `'summary'` by `createDeckBoot` → `seedCardSummaries`, so the
panel always has *something* to draw the instant a target is set.

**The cold-open target is one expression that already exists.** `CardGrid.tsx:76` is the sanctioned
flattening — copy it, do not write a second one:

```ts
const tiles = [...boards.commander, ...boards.mainboard.flatMap((group) => group.cards)]
```

`boards.mainboard` is in `TYPE_GROUPS` order with **empty groups omitted**, so `mainboard[0]` is
genuinely the first populated group. Both boards can be empty (`boardsOf([])`), so the default
target must be total.

**The right column is a placeholder waiting to be displaced.** `AppShell.tsx:131-136` renders
`slot(right, 'Card detail — c4-5 — the deck list — c4-7 — and the format check — c4-10 — stack
here.')`, and `App.tsx` does not pass `right` at all. **`AppShell.tsx` is not edited** — this is
c2-9's decide-once "displacement, not deletion" ruling, on its fifth application. `AppShell.test.tsx`
must still pass unchanged; `App.test.tsx` carries the assertion that changes.

**`Panel` gives the required semantics for free.** `Panel.tsx` renders
`<section aria-label={title}>` with the title as an `<h2 className="panel-title">`. So
`<Panel title="Card detail" level="overlay">` satisfies UX-DR44's *`role="region"` labelled "Card
detail"* with no ARIA written by hand. `Panel.css:45` already names this story: *"DESIGN.md's
`level="overlay"` panel — the card detail panel (c4-5)"*.

**The image URL is one function, and this story adds its first parameter.**
`src/containers/CardTile/imageUrl.ts:48`:

```ts
export const cardImageUrl = (cardId: string): string =>
  `/api/card-image/${encodeURIComponent(cardId)}`
```

Its docstring instructs this story directly: *"A caller that genuinely needs another size or another
face adds a parameter to THIS function"*, and *"the split it forces is the one that lets **c4-5** (a
larger detail render) and **c4-6** (`face=1`) extend ONE function rather than each writing a second
template string."* **`size` is deliberately unspelled today** because the URL is the browser's cache
key and `normal` is the route's default — which means `size=large` is a *different cache key*, and
detail art is cold on first inspection even when the grid is fully warm.

**The reduced-motion block already reserves this story's row.** `tokens.css:245-246`:

```
Detail-panel content swap  -> instant, no crossfade (it changes on
                              every hover)                        (c4-5)
```

**The refusal contract is pre-written.** `CardPlaceholder.tsx:59-68`, addressed to this story:

> *"Placeholder tiles behave like normal tiles (inspection contract) except the unknown-card
> variant, which cannot be inspected — there is nothing to show."* … **c4-5's tests prove the
> refusal; this file's API is what makes it easy to obey.**

### What the real data says (measured at `b26e8f4`, read-only, against the shipped database)

Measured with `sqlite3` in `mode=ro` against `src.paths.data_dir()/cards.db` (38,261 cards) and the
largest real deck (`Atraxa Counter Cabinet v2 (owned)`, 99 rows) — the same deck c4-4 measured.

**The finding that decides Q1 — hydration's real product:**

| Population | Count | Top-level `oracle_text` |
|---|---:|---|
| Cards with `card_faces` | 3,225 | **blank in 3,225 — 100%** |
| …of which carry per-face `image_uris` (→ c4-6 flip control) | 2,778 | blank |
| …of which are split/adventure (top-level image, no flip control) | 368 | blank |
| Cards whose `type_line` is literally `Card // Card` | 2,274 | blank |

So for **every** multi-faced card, `CardSummary` — the tier that arrives free with the deck payload
— gives a name like `Clearwater Pathway // Murkwater Pathway`, a type line like `Land // Land` (or
the degenerate `Card // Card`), an empty `mana_cost`, and an **empty `oracle_text`**. The real
per-face name, type line and rules text exist only in `card_faces`, which only `GET
/api/cards/{card_id}` returns. Verified on all six such cards in the real deck.

**The rest of the corpus:**

- `oracle_text` empty overall: **3,927 of 38,261**. `mana_cost` empty: **5,943** (lands).
- Longest `oracle_text` in the corpus: **1,489 chars** (`Baldur's Gate Wilderness`); only **5** cards
  exceed 700 and only **63** exceed 500.
- Cards with no usable image at `normal`: **79**. At **`large`: also 79** — the same set, so the
  named placeholder is exactly as reachable at detail size as it is in the grid, and no new
  no-image population appears at this story's size.

**In the 99-card deck this story will be eye-checked against:**

- `oracle_text` length: min **0**, median **156**, max **452** (`Vraska, Betrayal's Sting`). Seven
  cards exceed 300; **six** are blank.
- Six names contain `//` — all six are MDFC Pathway lands, all with per-face `image_uris`, all with
  blank top-level type/cost/oracle.
- Longest name: **42 chars** (`Barkchannel Pathway // Tidechannel Pathway`).
- One commander (`Atraxa, Praetors' Voice`), which is the first tile in the grid's visual order.

**What this means for the panel's layout:** the median card needs ~156 characters of body text and
the worst real card needs 452. The 1,489-char corpus outlier is the case that decides whether the
panel body scrolls or grows (Q10) — and it is the same question the inherited `overflow-wrap`
vertical-clipping deferral asks.

### The wire types — what the panel can and cannot draw

Import from `src/api/schema.ts` (the sanctioned barrel). **Never** import `./types` outside
`src/api/`, and never re-declare a wire shape — `tests/wire-contract.test.ts` derives its ban from
`openapi.json`'s `components.schemas` keys.

`CardSummary` (free, seeded for every deck card — all fields **required and non-nullable**):
`id`, `name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `rarity`, `set_code`.

`Card` (hydrated) adds: `printed_name?`, `oracle_id`, `power?`, `toughness?`, `game_changer?`,
`set_name`, `collector_number`, `color_identity`, `color_indicator?`, `keywords?`, `legalities`,
**`card_faces?: CardFace[] | null`**, `image_uris?: {…} | null`, `games`.

`CardFace` — every field optional **and** nullable, plus an open index signature:
`name?`, `mana_cost?`, `type_line?`, `oracle_text?`, `image_uris?`.

**There is no `prices` field, and there never has been.** `types.d.ts:325`: *"There is no price data
of any kind in this record."* The AC that says "no price is shown" is satisfied **by absence** — see
the inherited deferral below, which is homed on this story by name.

**`CardFace` has no alias yet.** `schema.ts:101` declined it: *"`CardFace` stays declined: **c4-6**
renders the flip control."* Q1's answer makes this story its first consumer, so the alias is added
here — a ledger correction, stated rather than silent.

**Do not read `image_uris` to build a URL.** `tests/no-scryfall-hosts.test.ts` bans the Scryfall host
family across all of `src/`; art goes through `cardImageUrl(cardId)` (AD-11).

### Decide-once rulings this story inherits (do not re-derive)

1. **`src/containers/` is where a component that BEHAVES lives** (c4-4 Q1, ruled *against* its own
   proposal). `src/components/` is a **closed set-equality category** — `shell.test.ts:1257` — and
   every member is banned from hooks, `on*` in either position, `ref` in either position, spread,
   and a value `react` import. A detail panel needs all of those. The posture, verbatim
   (`ui/README.md:565-569`): a container **MAY** hold state, call hooks of any family, declare and
   attach handlers, hold a `ref`, read the store through `src/state/`, and compose primitives. It
   may **NOT** reach the network (the door is still `src/api/client.ts`), import a state library
   directly, write a store slice from outside its own module, or declare a design token.

2. **The `CONTAINERS` guard is git-derived set equality, and it is red until you join it.**
   `shell.test.ts:1457` holds one entry per shipped container module with an **exhaustive** import
   list (CSS side-effect imports and `'react'` included), plus a non-vacuity pin
   `expect(CONTAINERS).toHaveLength(3)` at `:1560` that must be bumped in the same commit.
   `:1568-1570` names this story first among its inheritors.

3. **UX-DR4 card-radius exclusivity is a gate in both directions.** `.card-shape` in
   `src/styles/card-geometry.css` is the ONE declaration — consume it by class name, never import
   it, never re-declare `aspect-ratio` or `border-radius`. A card-shaped stylesheet joins
   `CARD_SHAPED` in `token-usage.test.ts:813` **with its reason**, and thereby also accepts the
   converse: **no chrome radius** (`--radius-sm/md/lg/pill`) may appear in that file. The shipped
   resolution is **two stylesheets, not an exception** — `CardTile.css` (card) and
   `QuantityBadge.css` (chrome) are the worked precedent, and this story's ring chrome hits the same
   collision.

4. **Every shadow and radius goes through a token; composites live in the layer.**
   `ui/README.md:301`: *"If you need a new composite (a live ring, a pinned ring), **add a token to
   the layer**; do not inline it, and do not declare it in your own file."* Both pins move together:
   `expectedNames` + `toHaveLength(66)` in `tests/tokens.test.ts:231,291`, and
   `declaredTokens.size` in `tests/token-usage.test.ts:1072`.

5. **The reduced-motion registration is a derived gate, not prose.** Any shipped block declaring
   `transform` — or the individual `scale:` / `rotate:` / `translate:` properties, per property
   after c4-4's review hardened it — must be neutralised `none !important` on the **same selector
   text** in `tokens.css`'s reduced-motion block. It compares selector *text*, not resolved
   specificity: a mismatched selector is a **false failure** whose repair is to write the matching
   selector. A motion expressed only as a duration is mechanical (the four `--motion-*` are zeroed);
   a transform or a crossfade registers explicitly.

6. **Nothing pulses, loops or alternates, at any setting.** `animation-iteration-count` may only be
   `1`; `infinite`/`alternate` are banned in every spelling by stylelint *and* by a shorthand parser.

7. **`:focus-visible`, never `:focus`; `outline: none` is banned in all four spellings.** The UA ring
   may only be **replaced** by an authored outline. Card-shaped focus uses
   `--shadow-focus-ring-over-art` + `outline: var(--focus-ring-width) solid var(--focus-ring)` at
   `outline-offset: 0`.

8. **`--accent-dim` on `--surface-overlay` is banned** (2.70:1). The guard is **same-block only** — a
   parent setting the overlay background and a child setting the dim border is *not* caught. Live
   and selected markers on overlay-backed surfaces use `--accent`.

9. **Emptiness is `filled()` / `typeof` + `trim()`, never truthiness; a number is `Number.isFinite`,
   never `count &&`.** The shared string-narrowing spelling is `given()`, duplicated verbatim in
   `CardPlaceholder.tsx:154` and `CardTile.tsx:158`; it returns the **trimmed** value.

10. **The name is announced once** (c4-4 Q4, ruled and eye-confirmed). c4-4's own second defect was
    a path where the tile would have spoken the card's name twice; the caption is now suppressed
    whenever the placeholder is naming the card. This story must answer the same question for a
    panel that renders a heading *and* an image *and* possibly a named placeholder (Q13).

11. **Every card name renders in CAPITALS by gate.** `font: var(--type-label)` obliges
    `letter-spacing: var(--tracking-label)` **and** `text-transform: uppercase` in the same block
    (`findRoleWithoutCompanions`); `font: var(--type-numeric)` obliges
    `font-variant-numeric: var(--type-numeric-features)` (`findUnpairedNumericRole`). The standing
    blind spot: **no gate asks whether the role suits the value** — that is review's, forever.

12. **`AppShell.tsx` is never edited; placeholders are displaced, not deleted** (c2-9, fifth
    application).

13. **A card refusal never puts a panel on the glass** (c4-1 AC 13, FR-13). `panelFor()` is not
    called on the card path. A consumer maps `entry.placeholder` to a variant and passes plain
    props; **nothing re-derives a placeholder from a wire token**, and a `switch (entry.reason)` in
    a component is the drift that field exists to prevent.

14. **The order the view draws is the store's, not a second sort.** A `sort()`, a `filter()` or a
    second grouping in this story is the drift `deckGroups.ts` was written to prevent (AD-12).

15. **`px` literals in `src/containers/` need a DESIGN.md citation within a sentence of the value**
   (`shell.test.ts:975`, scoped to a list of roots that c4-4 widened to include `src/containers/`).

### Latest technical specifics — zustand 5, React 19, and the hover path

**zustand `^5.0.14`** (`package.json`; a second state library is banned by
`tests/package-contract.test.ts` and by the `"//"` key in `package.json` itself).

- **v5 removed `create`'s equality-function argument and matches React's default referential
  comparison.** A selector that returns a **new object or array on every call** re-renders forever.
  This is the single most likely way to break a hover-driven panel, because the natural selector
  here — "give me the target id and whether it's pinned" — is exactly an object literal. Either
  select **one primitive per hook call**, or wrap with `useShallow`:

  ```ts
  import { useShallow } from 'zustand/shallow'
  const { targetId, pinned } = useStore(useShallow((s) => ({ targetId: s.targetId, pinned: s.pinned })))
  ```

  `createWithEqualityFn` from `zustand/traditional` is the v4-compatibility path and is **not** the
  house idiom — every shipped selector in `src/state/` returns a primitive or a stored reference
  (`useCardEntry` returns `state.cards[cardId]`, a stored object, which is stable). Prefer one
  primitive per call and keep `useShallow` for the case that genuinely needs two.

- **Subscription granularity is the whole argument for Q8.** `useCardStore((s) => s.cards[id])`
  re-renders only the components whose selected slice changed. A `live` flag threaded as a prop from
  `CardGrid` re-renders all 99 tiles on every hover; a per-tile selector re-renders exactly the two
  tiles whose liveness changed.

**React `^19.2.8`.** `useId()` is the shipped idiom for `aria-labelledby` wiring (`CardTile.tsx`).
Note the two `<img>` traps c4-4 documented and this story inherits at a **different cache key**:

- A cached image can fire `load` **before React attaches `onLoad`**, leaving a well forever.
  `settleIfCached` closes it by asking the element (`complete && naturalWidth > 0`) via a `ref`
  callback. c4-4's review found the mirror hole and fixed it there: a **cached failure**
  (`complete && naturalWidth === 0`) must settle the failed arm too. If this story draws its own
  `<img>`, it inherits both arms — and because `size=large` is a distinct cache key, the detail
  image is **cold on first inspection even when the grid is fully warm**, so the cold path is the
  common one here, not the exotic one.
- **jsdom sees neither half**: it loads no images, fires no `load`/`error`, and reports
  `naturalWidth: 0` always. Events are **dispatched** (`fireEvent.load(img)`), never awaited, and
  the warm-cache claim is checked by eye in Task 7.

### The sixteen things this story must not break

1. `AppShell.tsx` — **not edited**. `AppShell.test.tsx`'s right-column placeholder assertion must
   still pass, because the placeholder still fires whenever `right` is empty.
2. `CardTile`'s accessible name — exactly once, `Black Lotus ×4` spelling pinned by c4-4's review
   (`aria-labelledby` ID order, **with a space**).
3. `CardGrid`'s visual order and its `boards`-only prop — no second flattening, no re-sort.
4. `useCardEntry`'s "starts nothing" contract — do not add an effect or a fetch to it.
5. `hydrateCard`'s attempt cap, in-flight dedupe and never-rejects posture.
6. `Panel` is a primitive a consumer **may not restyle**. It is `overflow: hidden` with 12px body
   padding, so a child's `--shadow-rest` clips at the panel edge.
7. `.app-shell-columns` is the app's **single scroll container**. `shell.test.ts` bans
   `overflow: hidden|clip` on the roots and on that scroller — and **explicitly exempts this
   story's panel** (`:421-423`, `:1768`), which legitimately clips and is not a root.
8. The one network door stays `['src/api/client.ts']` (`posture.test.ts:320`).
9. `store-writes.test.ts`'s `STORES` table — a new slice is registered there with `store`/`owner`/
   `why`, and **no component calls `setState`**.
10. `tests/wire-contract.test.ts` — no re-declared wire shape outside `src/api/`.
11. The 66-token inventory and its two pins — moved together or the pair is wrong.
12. `CardPlaceholder`'s discriminated union — `variant="unknown-card" name="…"` must keep failing to
    compile. This story renders it; it does not reshape it.
13. `.card-shape`'s single declaration and `CARD_SHAPED`'s two directions.
14. The reduced-motion registration block — extended, never bypassed.
15. `tests/copy-rules.test.ts` — any authored string bans `!`, emoji, and "something went wrong",
    and lives in a `copy.ts` beside the component (`StatePanel/copy.ts`, `CardPlaceholder/copy.ts`,
    `Footer/copy.ts` are the three precedents).
16. Python is untouched. `uv run pytest` must stay at **2,447 passed / 1 skipped / 54 deselected**.

### Source tree — what exists, what this story touches

```
ui/src/
  App.tsx                                   MODIFY  — pass `right={…}`; nothing else
  App.test.tsx                              MODIFY  — the displacement assertion
  api/schema.ts                             MODIFY  — add the `CardFace` alias (Q1)
  api/schema.test.ts                        MODIFY  — pin it
  state/
    cards.ts        useCardEntry, hydrateCard, CardEntry      READ ONLY
    deck.ts         useDeckState, surfaceOf, Surface          READ ONLY
    deckGroups.ts   DeckBoards, CardGroup, boardsOf           READ ONLY
    inspection.ts                           NEW     — the slice (Q5)
    inspection.test.ts                      NEW
  containers/
    CardTile/CardTile.tsx                   MODIFY  — handlers + live ring (Q7)
    CardTile/CardTile.test.tsx              MODIFY
    CardTile/CardTile.css                   MODIFY  — the live-ring rule
    CardTile/imageUrl.ts                    MODIFY  — the `size` parameter
    CardGrid/CardGrid.tsx                   READ ONLY unless Q7 says otherwise
    CardDetail/CardDetail.tsx               NEW     — the panel
    CardDetail/CardDetail.test.tsx          NEW
    CardDetail/CardDetail.css               NEW     — card-shaped; joins CARD_SHAPED
    CardDetail/CardDetailChrome.css         NEW     — ring + unpin chrome (Q2/Q3)
    CardDetail/copy.ts                      NEW     — authored strings (Q3)
  styles/tokens.css                         MODIFY  — two composites + the motion row
ui/tests/
  shell.test.ts        CONTAINERS + toHaveLength(3 → 4)       MODIFY
                       (the guard globs `src/containers/*.ts(x)` and excludes `*.test.ts(x)`,
                        so one new module = one new entry; a split-out helper makes it 5)
  tokens.test.ts       expectedNames + toHaveLength(66 → 68)  MODIFY
  token-usage.test.ts  declaredTokens.size, CARD_SHAPED, motion pin  MODIFY
  store-writes.test.ts STORES                                 MODIFY
  package-contract.test.ts                  MODIFY only if Q9 adds a dependency
```

### The inherited deferrals — give each a disposition (AC 30)

C2 retro ruling **R2**: inherited deferrals are acceptance criteria at context time, and "not
mentioned" is a failure of the AC. Six entries are homed on this story by name; the line each lives
on in `deferred-work.md` is given so this is checkable rather than reassuring.

1. **`Panel`'s appearance is not dev-verified (`:1343`, `:3450`)** — re-homed from c2-9 to this
   story as *"the first real `level="overlay"` panel"*. This is an **eye-check obligation**, not
   code: a titled overlay Panel on a real screen, against `DESIGN.md`'s `components.panel` block.

2. **Prices (`:1993-2003`)** — ruled by Brad at c3-2 Q4: the endpoint ships **no price field**
   rather than a permanently-null one. Homed here because this is *"the only surface EXPERIENCE.md
   promises prices on… so it is the story that must either render nothing there deliberately or
   raise the import work as its own brief."* The cost of adding them is on the record: a new column
   or side table (Scryfall prices are per-printing and volatile), an importer change, a hand-written
   migration (no Alembic), a re-import of 38,261 rows, plus a staleness story.

3. **The card cache's terminal-after-three asymmetry (`:3372`)** — three transient failures make an
   id terminal for the tab's life while the whole-screen poller self-heals. c4-2 owns the fix
   (`resetCardCache()` on a recovery transition); **this story is named as the one that makes it
   visible**, because a hover sweep is what spends the attempts.

4. **The named placeholder's undeclared vertical edge (`:3685-3691`)** — `.card-placeholder` pairs
   `overflow: hidden` with the fixed 63:88 box and `justify-content: center`, so a taller-than-box
   stack clips at both edges with no clamp and no ellipsis. **Re-homed here**, *"which renders the
   same component at detail size where a clamp would be visible, or review."*

5. **`CardPlaceholder` renders a `<div>`, and `<button>` takes phrasing content only
   (`:3743-3748`)** — invalid HTML by the letter of the spec inside `CardTile`. **Homed here**,
   *"which mounts the same component as detail art and can re-decide with two consumers in view."*
   (Q11.)

6. **The reduced-motion transform guard compares selector text (`:3750`)** — a fallback whose
   selector differs from the motion's reads as unregistered. False failure, not false pass; the
   repair is to write the matching selector.

Two more are **not** homed here but will be touched and must not be silently re-opened: the
standalone `token-usage.test.ts` runner crash (prove guards through the full `npm test`, never a
single-file run), and the jsdom accessible-name spelling limit (assert membership and the pinned
spelling; how a screen reader phrases it is the epic checklist's).

### Open questions — answer these before writing code

**Q1. Does the panel hydrate, and what does hydration actually buy? — proposal: yes, and it buys
the multi-faced cards.**
Measured, `CardSummary` already carries `name`, `mana_cost`, `type_line` and `oracle_text` — every
text field `DESIGN.md:387` asks this panel to render. For a single-faced card `hydrateCard` adds
nothing drawable, so "the rest fills in place" would be vacuous. But **all 3,225 faced cards have a
blank top-level `oracle_text`** and 2,274 carry the degenerate `Card // Card` type line, so for them
hydration is the *only* source of a type line and rules text. Proposal: **call `hydrateCard` on
every inspection target change**, render from the summary tier immediately, and when a hydrated
`card_faces` arrives render the **front face** (`card_faces[0]`) name / type line / oracle text over
the combined top-level values. This makes the no-spinner AC real for the 6% that need it, warms the
cache for c4-6, matches AD-12 and story 4.1's own AC (*"the cursor sweeps the whole grid twice →
each distinct card is fetched at most once"*), and gives `deferred-work.md:3372` the visibility it
was promised. **Consequence: this story adds the `CardFace` alias to `schema.ts`**, which
`schema.ts:101` had assigned to c4-6 — a ledger correction, stated in the open.

**Q2. The pinned ring's contrast defect — proposal: `--accent`, following the M4/C3 precedent.**
`DESIGN.md:199` declares `pinned-ring: '0 0 0 1px {colors.accent-dim}'` while `:196` declares the
same component's `background: '{colors.surface-overlay}'`. `DESIGN.md:305,312` put that pairing at
**2.70:1** and ban it; `token-usage.test.ts` gates it (same-block only). This is exactly the defect
the UX gate closed as **M4/C3** for `card-tile.live-ring`, where the fix was to move to
`{colors.accent}` *"with the reason stated inline so it isn't 'corrected' back"* — and it was never
carried across. Options: **(a)** ship the ring as `--accent` and say why inline; **(b)** ship it
non-inset so it lands on `--surface-base` (3.30:1, passes) and declare the non-inset requirement,
which nothing currently states — note `deck-row.live-rule`, the nearest sibling, *is* explicitly
`inset`. Proposal: **(a)**, plus a one-line amendment to `DESIGN.md`'s `card-detail` block so the
artefact and the code agree.

**Q3. The unpin control is unspecified — proposal: a labelled text button in `Panel`'s `badges`
slot.**
UX-DR20 requires it (*"click the panel's unpin control to release"*) and no artefact gives it a
size, glyph, position, label or token. It must be a real `<button>` with a ≥24×24px hit box
(UX-DR47) and a visible `:focus-visible` ring (UX-DR46). Proposal: render it **only while pinned**,
in `Panel`'s existing `badges` slot, as a text button — no invented glyph, because
`DESIGN.md:415`'s brand rules already make a novel symbol a risk and UX-DR7 bans symbol-lookalikes.
Its string lives in `CardDetail/copy.ts` and joins the copy gates. **It also adds a Tab stop that
UX-DR40's enumerated order does not contain** — the order runs `… → deck rows → connection pill →
footer links`. Proposal: it sits inside the right column after the panel heading, and this story
**writes that down for c4-11** rather than leaving c4-11 to discover it.

**Q4. Two composite tokens, 66 → 68 — proposal: as described, both pins in the same commit.**
`--shadow-live-ring` (c4-4 Q2 assigned it here, and `tokens.test.ts:433` **asserts its absence**, so
that test goes red on purpose and is repaired in the same commit) and a pinned-ring composite.
Values byte-for-byte from `DESIGN.md` frontmatter — `card-tile.live-ring` is
`0 0 0 1px {colors.accent}, 0 0 20px {colors.accent-glow}` — subject to Q2 for the pinned one. Pins:
`expectedNames` + `toHaveLength` in `tokens.test.ts:231,291`, `declaredTokens.size` in
`token-usage.test.ts:1072`.

**Q5. Where does inspection state live — proposal: a new `src/state/inspection.ts` slice, with the
spine sentence narrowed in writing.**
`deck.ts`'s header quotes the spine: *"its state comes from exactly two inputs — REST responses and
WebSocket messages. Nothing else may write the store."* A hovered or pinned card is a **third kind
of input**, and this is the first story to introduce one. Proposal: a fourth `create()` call in
`src/state/inspection.ts`, registered in `store-writes.test.ts`'s `STORES` with its `why`, holding
exactly two values (`hoveredId: string | null`, `pinnedId: string | null`) plus its own actions —
and the spine sentence narrowed **explicitly in the module header** to *"nothing outside the store
writes **server-derived** state"*, so the next reader does not have to guess. The counterweight to
argue against, not around: **c4-4 Q8 ruled per-tile state must not be lifted** (*"99 tiles sharing
one loaded-set in the store is a store write this story is not allowed to make"*). That was 99
values; this is one, and it is read by components in two different subtrees.

**Q6. It must live at app scope, not inside the deck view.** `EXPERIENCE.md:90` requires that *"the
pinned target survives closing the view"*, so Epic 6's agent views set and read the same slice. A
module-level zustand store satisfies this for free; a React context scoped under the left column
would not. Recorded so it is not re-litigated at c6-7.

**Q7. How does a tile learn it is live — proposal: a per-tile selector, not a threaded prop.**
Options: (a) `CardGrid` computes `live` and passes it to all 99 tiles; (b) each tile calls a
`useIsLiveTarget(cardId): boolean` selector exported from the slice. Proposal: **(b)**. Under
zustand v5 a selector returning a boolean re-renders only the tiles whose value changed — **exactly
two per hover** — whereas (a) re-renders all 99 on every cursor movement across the grid, on the
sweep this whole cache exists to make cheap. It also keeps `CardGrid`'s props at `{ boards }` and
lets c4-7's deck rows use the identical hook without going through the grid.

**Q8. What is the inspection slice's public API — proposal: location-agnostic verbs.**
c4-7 (deck rows), c4-6 (flip, which must **not** touch inspection) and c6-5..c6-8 (agent-view
thumbnails) all consume this. Proposal: `setHovered(cardId | null)`, `togglePin(cardId)`,
`clearPin()`, plus `useInspectionTargetId()` and `useIsLiveTarget(cardId)` — nothing named for a
tile, and no component calling `setState`. c4-6's control calls **none** of them and relies on
`stopPropagation`, so this story's tile handlers must be written so a child control can stop
propagation out of them.

**Q9. Hover has no test instrument — proposal: `fireEvent`, no new dependency.**
There is no `userEvent` anywhere in `ui/`, and `@testing-library/user-event` is not a dependency;
`tests/package-contract.test.ts` pins the list, so adding it is a decision with a diff. Proposal:
drive `fireEvent.mouseEnter/mouseLeave` and `.focus()`/`.blur()` directly, matching the suite's only
existing DOM-event idiom (`fireEvent.load`/`.error` in `CardTile.test.tsx`). Note the jsdom limit to
declare: **`fireEvent.mouseEnter` dispatches the event but jsdom evaluates no CSS**, so hover
*appearance* stays a source claim and only the *wiring* is provable.

**Q10. Does the panel body scroll or grow — proposal: internal scroll, with the clamp declared.**
Longest real oracle text is 452 chars; the corpus worst case is 1,489. `.app-shell-columns` is the
app's single scroll container and `shell.test.ts` **already exempts this story's panel** from the
clip ban, which is a decision made in advance and should be used. Proposal: the panel's text body
gets its own `overflow-y: auto` so a 1,489-char card cannot push the deck list and format check off
the screen — and this is the disposition for inherited deferral 4 (the placeholder's undeclared
vertical edge), because the clamp becomes visible at detail size.

**Q11. `<div>`-in-`<button>`, re-decided with two consumers — proposal: no change, scope narrowed.**
In this panel the placeholder is **not** inside a `<button>` — the detail art is not clickable — so
the spec violation does not recur here. Proposal: leave `CardPlaceholder`'s root a `<div>`, and
narrow the residue in `deferred-work.md` from "the primitive" to "the tile's mounting of it", which
is where it actually lives. Changing the primitive's root now would be a change made for one
consumer against the other's interest.

**Q12. Esc is layered, and Epic 6 must win — proposal: write the contract now.**
UX-DR39: *"Esc closes the topmost thing (open agent view first, then an active pin)."* No overlay
exists yet, so this story cannot test the layering. Proposal: this story registers a document-level
`keydown` that releases the pin **and documents in the module header that c6-5's agent view
registers earlier and calls `stopPropagation`**, so neither story edits the other's handler. State
the untestable half plainly rather than claiming coverage.

**Q13. Alt text — proposal: `alt=""` on the detail art, diverging from UX-DR48's literal words.**
UX-DR48 keeps `alt={name}` on the detail panel *"because there the image is the only carrier"* —
which is **measurably false for this component**, exactly as c4-4 found for the tile: the panel
renders the name in `--type-heading` immediately beneath the art. c4-4's Q4 ruled the name is
announced **once**. Proposal: follow the ruling (`alt=""`, the heading carries the name), state the
divergence from UX-DR48 in the open, and add it to the epic manual-testing checklist for a real
screen reader.

**Q14. What does the right column do when the left column falls to a state panel? — proposal:
hide it, and close the UX gate's open low.**
This is a **known, unactioned gap in the UX contract**, not an oversight of this story:
`validation-report-2026-07-25.md:78` records it as **L8** — *"Right-column panel visibility is
specified for cold-open-no-deck but not for the database-not-initialized or disconnected states,
which also put a State panel in the left column"* — and `:146` records the lows as unactioned.
`EXPERIENCE.md:112` covers only the cold-open-no-deck case (*"Right column panels hidden"*), while
`:98`/UX-DR30 says *"the right column, nav and footer remain functional around it"*. This story is
where the contradiction becomes code, because `surfaceOf()` already returns
`{ kind: 'panel', panel }` for all six state keys and `App.tsx` must decide what to pass as `right`.
Proposal: render the detail panel **only when `surface.kind === 'deck'`**, matching the one case the
contract does specify and keeping UX-DR20's *"never empty while a deck is loaded"* literally true —
a persistent panel with no deck behind it has nothing to be never-empty about. State the ruling so
c4-7 and c4-10 inherit it rather than each re-deciding.

**Q15. Cold-open target — proposal: the grid's visual order, which starts with the commander.**
UX-DR20 says *"the first card of the first type group"*. `boards.commander` is a separate board that
the grid draws **first**, so the literal reading and the on-screen reading differ whenever a deck
has a commander (measured: the real deck's first tile is `Atraxa, Praetors' Voice`). Proposal: use
`[...boards.commander, ...boards.mainboard.flatMap((g) => g.cards)][0]` — the same expression
`CardGrid.tsx:76` already uses — so the panel targets **what the eye lands on first**. Both boards
can be empty, so the resolution must be total; c4-12 owns the empty-deck copy.

## Acceptance Criteria

### The category, the store and the wiring

1. The panel lands in **`src/containers/CardDetail/`** as `CardDetail.tsx` + stylesheet(s) +
   colocated `CardDetail.test.tsx`, following the directory-per-component, no-barrel, flat
   kebab-case-class convention. It is **not** added to `src/components/`.
2. Every new container module is added to `CONTAINERS` in `ui/tests/shell.test.ts` in the **same
   commit**, with an **exhaustive** import list (CSS side-effect imports and `'react'` included),
   and the non-vacuity pin at `:1560` is bumped from `3` to the new count.
3. Inspection state lives in a new slice under `src/state/`, registered in
   `ui/tests/store-writes.test.ts`'s `STORES` table with `store` / `owner` / `why`. **No component
   calls `setState`.** The module header states explicitly how the spine's "exactly two inputs"
   sentence is narrowed to admit user interaction (Q5).
4. The slice's API is **location-agnostic** — nothing in its names refers to a tile — so c4-7's deck
   rows and Epic 6's thumbnails consume it unchanged (Q8).
5. The store lives at module scope, so a pinned target survives an agent view opening and closing
   (`EXPERIENCE.md:90`) (Q6).
6. `App.tsx` passes the panel as `AppShell`'s `right` prop. **`AppShell.tsx` is not edited** and
   `AppShell.test.tsx` passes unchanged; `App.test.tsx` carries the displacement assertion, and
   asserts the string `c4-5` is no longer on a rendered deck view.

### The panel — presence, content and the never-empty rule

7. With a deck loaded, the panel is **always present** in the right column at `level="overlay"`,
   rendered through the existing `Panel` primitive with `title="Card detail"` — which supplies
   `role="region"` labelled "Card detail" via `<section aria-label>` and an `<h2>` (UX-DR44).
8. On cold open the panel **targets a card with no interaction** and is never empty while a deck is
   loaded (FR-17, UX-DR20). The target is taken from the grid's own visual-order expression, not a
   second flattening (Q15, AD-12).
9. The resolution is **total**: a deck with an empty commander board and an empty mainboard produces
   no crash and no stray header. (The empty-deck *copy* is c4-12's.)
9a. What the right column does when the left column falls to a **state panel** is ruled and written
   down, and the ruling is stated as closing UX validation **L8**, which is open and unactioned in
   the artefact (Q14). Whatever is ruled, c4-7 and c4-10 inherit it rather than re-deciding.
10. Hovering **or** focusing a card tile updates the panel in place (UX-DR14, UX-DR39 — full focus
    parity; hover is never the only path).
11. The panel renders, in `DESIGN.md:387`'s order and roles: the card face at `size=large` at the
    **card radius and 63:88 aspect**; the name in `--type-heading`; the mana cost right-aligned; the
    type line in `--type-body` `--text-secondary`; the oracle text in `--type-body`
    `--text-secondary`.
12. Name and cost render **immediately** from the summary tier at the moment of hover; the rest
    fills in place; **there is no spinner anywhere** (UX-DR36).
13. For a card whose `card_faces` is present, the panel renders the **front face's** name, type line
    and oracle text once hydration lands — because the top-level values are blank or degenerate for
    100% of that population (Q1). Before hydration lands it shows what the summary has, and does not
    blank anything it was already showing.
14. **No price is rendered** — not a zero, not a placeholder, not an empty slot. The endpoint carries
    no price field; the AC is satisfied by absence, and the story record says so (deferral 2).
15. Art is routed through `cardImageUrl`, extended with a `size` parameter — **one function, not a
    second template string** (`imageUrl.ts:33`). No Scryfall host appears in `src/`.
16. A card with no image data at `large` renders `CardPlaceholder`, not a broken-image glyph — the
    same 79-card population as the grid, measured.
17. The **unknown-card variant cannot become the inspection target**, and a test proves the refusal
    (`CardPlaceholder.tsx:59-68`, UX-DR22).
18. A card refusal never puts a state panel on the glass — `panelFor()` is not called on this path,
    and no component switches on `entry.reason` (c4-1 AC 13, FR-13).

### Pinning, release and announcement

19. A click, or Enter on a focused card, **pins** the target: it is fixed, the panel carries the
    pinned ring, and hover no longer overrides it (UX-DR20).
20. The pin releases on: a second click of the same card, **Esc**, or the unpin control. Hover
    resumes control on release (UX-DR20, UX-DR39). Release is a **second single click** — no
    double-click semantics (UX-DR39, banned).
21. The unpin control is a real `<button>` with a ≥24×24px hit box and a `:focus-visible` ring
    (UX-DR47, UX-DR46), rendered only while pinned. Its string lives in a `copy.ts` beside the
    component (Q3).
22. Esc's layering is written down: the pin is released only when no agent view is open, and the
    module header states the contract c6-5 will rely on (Q12, UX-DR39).
23. A pin announces **exactly once**, through a **separate** polite live region:
    `Pinned — {card name}` (UX-DR45). The exact string, including whether it carries a trailing
    period, is fixed in `copy.ts` and pinned by test — `EXPERIENCE.md:154`'s worked example has one
    and the epic's template does not.
24. **The panel is not a live region and transient changes announce nothing** (UX-DR44, UX-DR45).
    This was a found-and-fixed defect at the UX gate (H4/C1), not a style preference — a test asserts
    the absence of `aria-live` on the panel, so a later story cannot reintroduce it silently.
25. **The panel is not a modal**: no focus trap, no return-focus contract, no `aria-modal`
    (confirmed Ruling 3; UX-DR38 — it *"neither stacks nor traps"*).
26. The panel exposes a heading that **c4-11's skip link can move focus to** — the heading is the
    literal string "Card detail", not the card name.

### Tokens, geometry, motion and focus

27. Two composites are added to `tokens.css` — the tile's live ring and the panel's pinned ring —
    with values byte-for-byte from `DESIGN.md` frontmatter subject to Q2's ruling. **Both pins move
    in the same commit**: `expectedNames` + `toHaveLength` in `tests/tokens.test.ts`, and
    `declaredTokens.size` in `tests/token-usage.test.ts`. `66 → 68`.
28. `tokens.test.ts:433`'s *"does NOT ship the live ring"* test is **repaired, not deleted** — it is
    the mechanism that told this story the pin moves, and its replacement asserts the token now
    exists with its DESIGN.md value.
29. The detail-art stylesheet joins `CARD_SHAPED` in `token-usage.test.ts` **with its reason**, and
    consequently spends **no chrome radius**. Ring and unpin chrome go in a **second stylesheet**,
    following the `CardTile.css` / `QuantityBadge.css` precedent.
30. The detail art carries `.card-shape` by class name and re-declares neither `aspect-ratio` nor
    `border-radius` (UX-DR4).
31. **No `--accent-dim` on `--surface-overlay`** anywhere in this story's stylesheets (UX-DR6,
    2.70:1). Live and pinned markers use `--accent`.
32. Under `prefers-reduced-motion: reduce` the **content swap is instant with no crossfade** — it
    changes on every hover, so it must never animate (UX-DR42). If any transform ships, it is
    registered `none !important` on the **matching selector text** in `tokens.css`'s reduced-motion
    block, and the enumerated shipped-motion pin in `token-usage.test.ts` moves in the same commit.
33. Nothing pulses, loops or alternates at any setting.
34. The tile's live ring uses `:focus-visible`, never `:focus`; no `outline: none` in any spelling;
    any raised z-index stays below the overlay layer's `20`.
35. Every `px` literal in the new stylesheets carries a DESIGN.md citation within a sentence of the
    value.

### The record, the gates and the ledger

36. **Each of the six inherited deferrals homed on this story gets a written disposition** — done,
    declined with a reason, or re-homed by name (C2 retro ruling R2). Deferral 1 (`Panel`'s
    overlay appearance) is an **eye-check**, and it is performed, not assumed.
37. Every claim the jsdom suite **cannot** carry is declared, not implied: hover *appearance*,
    the reduced-motion media query, the accessible-name spelling as a screen reader phrases it, and
    the warm/cold `size=large` image race.
38. Evasion probes are run against every new guard, and **a probe that passes is recorded**, not
    quietly fixed — c4-3's probe (j) and c4-4's probe (e) are the precedent.
39. Ten gates green: `npm run lint`, `npm run format:check`, `npx tsc -b --force`, `npm test`,
    `npm run build`; `uv run pytest`, `ruff check`, `ruff format --check`, `mypy src/`,
    `mypy src/ --platform win32`. **`tsc -b --force`, not `tsc -b`** — the cache hides `TS2835`
    cascades. Guards are proven through the **full `npm test`**, never a standalone file run.
40. The bundle is rebuilt and the `plugin/` mirror regenerated, both measured against c4-4's
    baseline (`index-mnVGJAvJ.js` **208,004 B**, `index-Cgivw4Tq.css` **11,579 B**) and reported as
    changed or byte-identical with the numbers. This story mounts a new component, so the JS bundle
    **must** change — a byte-identical JS bundle here means it did not ship.

## Tasks / Subtasks

- [x] **Task 0 — Answer the fifteen open questions** (AC 1–40 depend on them). Cut the story branch
      `feat/companion-c4-5-card-detail-panel` from `b26e8f4`. Record each answer in the story before
      writing code; do not start with an unanswered Q1, Q2, Q3, Q5 or Q7.
- [x] **Task 1 — The inspection slice** (AC 3, 4, 5, 8, 9)
  - [x] `src/state/inspection.ts`: the store, the actions, `useInspectionTargetId`,
        `useIsLiveTarget`, and the module header narrowing the spine sentence.
  - [x] Register it in `ui/tests/store-writes.test.ts`'s `STORES`.
  - [x] Cold-open resolution from `boards`, total over both empty boards.
  - [x] `src/state/inspection.test.ts`.
- [x] **Task 2 — Tokens and geometry first** (AC 27–31, 35)
  - [x] Add both composites to `tokens.css`; move **both** pins; repair `tokens.test.ts:433`.
  - [x] Add the detail-art stylesheet to `CARD_SHAPED` with its reason; put chrome in a second file.
  - [x] Extend `imageUrl.ts` with the `size` parameter and its test.
- [x] **Task 3 — The panel** (AC 7, 10–18, 26)
  - [x] `CardDetail.tsx` through `Panel title="Card detail" level="overlay"`.
  - [x] Summary-tier render, `hydrateCard` on target change, front-face resolution from
        `card_faces[0]`, `CardFace` alias added to `src/api/schema.ts` and pinned in `schema.test.ts`.
  - [x] Placeholder path at detail size; unknown-card refusal.
  - [x] Panel body scroll / clamp (Q10) — the disposition for inherited deferral 4.
- [x] **Task 4 — The tile learns to respond** (AC 10, 19, 34)
  - [x] Handlers on `CardTile`'s existing `<button>`; the live-ring rule in `CardTile.css`.
  - [x] Written so a child control can `stopPropagation` out of them (c4-6's flip control).
- [x] **Task 5 — Pin, release, announce** (AC 19–25)
  - [x] `copy.ts` with the unpin label and the pin announcement; joins the copy gates.
  - [x] The separate polite region; a test asserting the panel itself carries **no** `aria-live`.
  - [x] Esc handling plus the written layering contract for c6-5.
- [x] **Task 6 — Mount it** (AC 6)
  - [x] `App.tsx` passes `right`; `App.test.tsx` displacement assertion; `AppShell.tsx` untouched.
  - [x] The `surface.kind === 'panel'` branch, per Q14's ruling, with its test (AC 9a).
- [x] **Task 7 — Prove it, and declare what cannot be proven** (AC 36–40)
  - [x] Evasion probes against every new guard; record any that pass.
  - [x] Eye-check in a real browser against the running backend and the 99-card deck: the titled
        `level="overlay"` Panel (deferral 1), the pinned and live rings, the cold `size=large` first
        paint, and the longest-oracle card's layout.
  - [x] Dispositions for all six inherited deferrals; declare the four unprovable claims.
  - [x] Ten gates; rebuild bundle + mirror; report the byte counts.
- [x] **Task 8 — Set status `review` and STOP.** Do not raise the PR — Brad runs the three-layer
      review and raises it.

### Review Findings

Three-layer review 2026-08-05 (Blind Hunter / Edge Case Hunter / Acceptance Auditor). 26 raw
findings → 3 decision-needed, 11 patch, 0 defer, 9 dismissed (given()-third-copy ratified at its
own recorded threshold; setHovered(null) arm deliberate per Q8; unknown cold-open resting state
declared in-code with zero population; blank card_id hypothetical behind the backend PK +
hydrateCard's terminal refusal; App.test id- stub is fixture convention; announcement re-fire on
surface-flip remount is defensible context re-establishment; hover/focus single-slot
mixed-modality erase is the deliberate Q8 single-slot design; AC 35 + AC 40 auditor observations
were explicitly non-findings; auditor confirmed 38/41 ACs satisfied).

- [x] [Review][Decision→Patch] Inspection state survives deck replacement — RULED (Brad,
      2026-08-05): clear hover+pin in the existing `boards` effect. The caveat is accepted: a
      same-deck edit also fires the effect and releases a pin, and that is rarer and less wrong
      than a pinned card from a previous deck outranking the new deck's cold-open target.
      Becomes a patch below.
- [x] [Review][Decision→Defer] The 21em oracle scroller is keyboard-unreachable — RULED (Brad,
      2026-08-05): ledger to c4-11, the keyboard/focus story that owns the Tab-order additions.
      Reason: the standard fix breaks the AC 25 `[tabindex]`-absence test and adds a Tab stop
      UX-DR40 doesn't enumerate — both are c4-11's to renegotiate, not this story's.
- [x] [Review][Decision→Patch] Unpin destroys the focused element — RULED (Brad, 2026-08-05):
      when the unpin button is activated, move focus to the panel's `<h2>` — the element c4-11's
      skip link already targets, so both stories converge on one focus home. Becomes a patch
      below.
- [x] [Review][Patch] Clear hover+pin when `boards` changes (D1's ruling)
      [ui/src/containers/CardDetail/CardDetail.tsx:259]
- [x] [Review][Patch] Move focus to the panel `<h2>` on unpin activation (D3's ruling)
      [ui/src/containers/CardDetail/CardDetail.tsx:304]
- [x] [Review][Patch] Multi-line oracle text collapses to one paragraph — no
      `white-space: pre-line`, so `\n`-separated abilities run together for most of the corpus
      [ui/src/containers/CardDetail/CardDetailChrome.css:117]
- [x] [Review][Patch] AC 6 second half missing — no `c4-5`-absence displacement assertion in
      App.test.tsx; Task 6 checkbox claims it exists [ui/src/App.test.tsx:470]
- [x] [Review][Patch] AC 9a test missing — nothing asserts the detail panel is absent while a
      state panel occupies the glass (`surface.kind === 'panel'` branch untested)
      [ui/src/App.tsx:181]
- [x] [Review][Patch] Q3's promised Tab-stop record absent — the c4-11 Tab-order note the Task 0
      record and the test comment both claim is "in the module header" is nowhere in
      CardDetail.tsx [ui/src/containers/CardDetail/CardDetail.tsx:1]
- [x] [Review][Patch] Esc handler ignores `isComposing`/`defaultPrevented` — an IME-cancel Esc
      releases the pin once any text input exists [ui/src/containers/CardDetail/CardDetail.tsx:279]
- [x] [Review][Patch] The written c6-5 Esc layering contract has a hole — an element-scoped
      `stopPropagation` cannot pre-empt this document-level listener when focus sits outside the
      overlay subtree; correct the contract text in both module headers
      [ui/src/state/inspection.ts:57, ui/src/containers/CardDetail/CardDetail.tsx:83]
- [x] [Review][Patch] A pin of a name-less cache entry announces `''` forever — allow one late
      capture when the name arrives so AC 23's "exactly once" cannot silently become zero
      [ui/src/containers/CardDetail/CardDetail.tsx:250]
- [x] [Review][Patch] Failed-art placeholder renders outside `.card-detail-art` and drops
      `--shadow-rest` — wrap it in the art box the way the loading well already is
      [ui/src/containers/CardDetail/CardDetail.tsx:324]
- [x] [Review][Patch] Stale pin pointer in the c4-4 comment — `toHaveLength(66)` cited 8 lines
      above the block that moved it to 68 [ui/src/styles/tokens.css:211]
- [x] [Review][Patch] The type-only probe tests a private regex copy, not the production scan —
      extract one shared constant so the firing half cannot go vacuous again
      [ui/tests/shell.test.ts:1718]
- [x] [Review][Patch] MDFC pin announcement speaks the combined name while the panel renders the
      face name — record the divergence in the declared-divergences note / epic manual-testing
      checklist [ui/src/containers/CardDetail/CardDetail.tsx:250]

**PR #44 review (Greptile, 2026-08-05) — one P1, and it OVERTURNED a triage dismissal.**
"Mixed input state clears inspection" (`CardTile.tsx:261-263`) is the same finding the Edge Case
Hunter raised and triage dismissed as "deliberate Q8 single-slot design, niche sequence" — two
independent reviewers flagging the identical seam retired that rationale. Fixed as TWO SLOTS
plus recency: `hoveredId` (pointer) and `focusedId` (keyboard) with a `lastTransient` tag,
resolution `pin ?? last-used-transient ?? other-transient ?? default`; clears stay keyed by id
per modality and do not rewrite recency. New verbs `setFocused`/`clearFocused` +
`clearTransientTargets` (the deck-transition clear); `setHovered`'s `null` arm removed (its
dismissal fell with the same ruling). A fixed precedence in either direction would have
regressed a real case — pointer-over-focus masks active Tab-navigation behind a resting mouse;
focus-over-pointer masks the core hover sweep behind a forgotten focus ring — recency is the
only resolution matching what the eye is doing in both. 1,174 → 1,181 tests (7 new: both
stranded-modality directions at slice and tile, recency both orders, clear-preserves-recency,
focus refusal, deck-transition clear); bundle JS 213,797 B, CSS unchanged, mirror byte-identical.

**Review outcome (2026-08-05).** All 13 patches applied, all gates green: **1,174 frontend tests
(was 1,165 — five new: deck-replacement clears the inspection, same-deck remount does not, unpin
hands focus to the `<h2>`, the late announcement, and the pre-line source pin), tsc, eslint,
stylelint.** One new container — `CardDetail/deckMemory.ts` (the deck-transition memory; its own
module per `imageUrl.ts`'s `react-refresh` precedent) — moves the CONTAINERS pin 6 → 7.
Bundle rebuilt + mirror synced byte-identical: JS **213,482 B** (`index-Cox3cQoE.js`, was
213,053), CSS **13,452 B** (`index-tvpYICK1.css`, was 13,431). The oracle-scroller deferral and
the MDFC-announcement checklist entry are ledgered in `deferred-work.md` under this review's
heading.

### References

- Story 4.5 and the UX-DR inventory: [epics-companion-app.md:1993-2033](../planning-artifacts/epics-companion-app.md), UX-DR20 `:442`, UX-DR36 `:541`, UX-DR38 `:553`, UX-DR39 `:558`, UX-DR42 `:577`, UX-DR44 `:590`, UX-DR45 `:597`, UX-DR47 `:608`, UX-DR48 `:611`; rulings 2 and 3 confirmed at `:624-641`
- Visual contract: [DESIGN.md:195-199](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md) (`card-detail` block), `:387` (anatomy), `:305,312` (the contrast bans), `:362,366` (card geometry; the mock is not authoritative)
- Behavioural contract: [EXPERIENCE.md:86](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md), `:51` (overlay depth), `:90` (pin survives a view close), `:103` (refetch), `:138-147` (interaction primitives), `:152` (reduced motion), `:154,158` (semantics and live regions), `:166` (skeleton vs placeholder)
- UX gate: [validation-report-2026-07-25.md:47](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/validation-report-2026-07-25.md) (H4), `:85` (C1), `:57,87` (M4/C3 — the ring precedent this story must carry across), `:78,146` (L8 — right-column visibility during a state panel, open and unactioned, Q14), `:45,86` (H3/C2 — the skip link targets this panel's heading)
- Architecture: [ARCHITECTURE-SPINE.md:272-290](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) (AD-12, which names this panel as the reason the cache exists), `:242-270` (AD-11), `:329-352` (AD-16)
- Conventions: `ui/README.md:545-569` (containers), `:779-834` (the card shape), `:858-893` (motion, the focus ring, the absent live-ring token), `:1200-1244` (the store, the one door, the no-panel-on-a-card-refusal rule), `:1331-1342` (the `Panel` eye-check homed here)
- Ledger: `deferred-work.md:1343`, `:1993-2003`, `:3372`, `:3685-3691`, `:3743-3748`, `:3750`
- Previous story: [c4-4-card-tile-and-the-card-art-grid.md](c4-4-card-tile-and-the-card-art-grid.md) — Q1 (containers), Q2 (the live-ring deferral), Q4 (the name announced once), Q8 (per-tile state not lifted)

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Opus 5, 1M context) via Claude Code / BMAD `dev-story`.

### Debug Log References

#### Task 0 — the fifteen answers, recorded before any code was written

Branch `feat/companion-c4-5-card-detail-panel` cut from `b26e8f4`.

**Every measured number in the story record was re-verified read-only against the shipped
database first, and every one held.** 38,261 cards; `card_faces` present **3,225**, of which
**3,225** have a blank top-level `oracle_text` (100%); `type_line = 'Card // Card'` **2,274**;
blank `oracle_text` overall **3,927**; blank `mana_cost` **5,943**; longest `oracle_text`
**1,489**, with **5** over 700 and **63** over 500; cards with no usable image at `normal`
**79** and at `large` **79** — the same set. In the largest real deck (99 rows): **6** names
contain `//`, all six MDFC Pathways, all six with a blank top-level `oracle_text` and the
degenerate `Land // Land` type line; longest name **42** characters.

One correction to the record, immaterial to every ruling: there are **two** 99-row decks on
this machine (`Atraxa Counter Cabinet v2 (owned)` and `Atraxa Counter Cabinet`). The story's
oracle-length figures (median 156 / max 452) are the first one's; the second measures median
145 / max 530. Both are far under the 1,489-character corpus outlier that decides Q10, so the
ruling is unchanged and the number is stated rather than smoothed over.

**Q1 — AS PROPOSED.** Hydrate on every target change; render the summary tier immediately;
when a hydrated `card_faces` arrives, render **`card_faces[0]`**'s name / type line / oracle
text over the blank top-level values. `CardFace` is added to `src/api/schema.ts` — it IS a
`components.schemas` key, so the alias is the sanctioned spelling and `wire-contract.test.ts`
bans any other. The ledger correction stated in the open: `schema.ts:101` had assigned it to
c4-6.

**Q2 — AS PROPOSED, option (a).** The pinned ring ships as `--accent`, and `DESIGN.md`'s
`components.card-detail.pinned-ring` is amended from `{colors.accent-dim}` to `{colors.accent}`
with the reason inline — the identical repair the UX gate made as **C3** for
`card-tile.live-ring` and never carried across. The artefact is amended rather than
contradicted because `tokens.test.ts` asserts token values **byte-for-byte against DESIGN.md's
frontmatter**: shipping `--accent` against an artefact that says `accent-dim` would be a red
test, and shipping `accent-dim` to satisfy it would be a 2.70:1 accessibility defect.

**Q3 — AS PROPOSED.** A real `<button>` in `Panel`'s existing `badges` slot, rendered only
while pinned, carrying a text label (no invented glyph) from `CardDetail/copy.ts`. Its hit box
clears 24×24 by arithmetic rather than by a `px` literal: `--type-label` is `500 11px/1.3`
(14.3px) plus `padding: var(--space-2) var(--space-3)` (8px top and bottom) = **30.3px** tall.
The Tab stop it adds is written down for **c4-11** in the module header.

**Q4 — AS PROPOSED.** `--shadow-live-ring` and `--shadow-pinned-ring`; **66 → 68**, with
`expectedNames` + `toHaveLength` in `tokens.test.ts` and `declaredTokens.size` in
`token-usage.test.ts` moved in the same commit. `tokens.test.ts:433`'s *"does NOT ship the live
ring"* is **repaired, not deleted**.

**Q5 — AS PROPOSED, with one deviation stated.** A new `src/state/inspection.ts` slice, a
fourth `create()`, registered in `STORES`, with the spine sentence narrowed **in the module
header** to *"nothing outside the store writes **server-derived** state"*. The deviation: the
slice holds **three** values, not the proposed two. `defaultId` is the cold-open resolution,
and it has to be in the store rather than threaded, because `useInspectionTargetId()` takes no
argument (Q8) and `useIsLiveTarget(cardId)` is called by a tile that does not know the boards —
so the cold-open target would otherwise be a target the panel could see and the tile could not,
i.e. two resolutions of one concept. One resolution, one place.

**Q6 — RECORDED.** Module-scope store, so a pinned target survives an agent view opening and
closing (`EXPERIENCE.md:90`). Nothing for c6-7 to re-litigate.

**Q7 — AS PROPOSED, option (b).** `useIsLiveTarget(cardId)` returns a **boolean primitive**,
so zustand v5's referential comparison re-renders exactly the two tiles whose liveness changed
rather than all 99 on every cursor movement. `CardGrid` keeps its `{ boards }` prop and is not
edited.

**Q8 — AS PROPOSED, plus one addition.** `setHovered`, `togglePin`, `clearPin`,
`useInspectionTargetId`, `useIsLiveTarget` — nothing named for a tile. The addition is
`clearHovered(cardId)`, which clears only if that id is still the hovered one: a bare
`setHovered(null)` on `blur`/`mouseleave` loses a race with the `focus`/`mouseenter` of the
tile being moved to, and the visible result is the panel snapping back to the cold-open card
mid-sweep. Handlers are attached to the tile's own `<button>`, so a child control (c4-6's flip)
suppresses them with `stopPropagation` — stated in both module headers.

**Q9 — AS PROPOSED.** `fireEvent.mouseEnter/mouseLeave` + `.focus()`/`.blur()`. No new
dependency; `package-contract.test.ts` is untouched. The jsdom limit is declared: the event is
dispatched and no CSS is evaluated, so hover **wiring** is provable and hover **appearance** is
not.

**Q10 — AS PROPOSED, with the clamp expressed in `em`.** The oracle block gets its own
`overflow-y: auto` at `max-height: 21em` — `{typography.body}` is `14px/1.5`, so one line is
`1.5em` and the cap is **fourteen lines**. `em` rather than `px` (no citation owed, and no
`lh`-support cliff that would drop the declaration silently). This is the disposition for
inherited deferral 4.

**Q11 — AS PROPOSED.** `CardPlaceholder`'s root stays a `<div>`; the residue narrows from "the
primitive" to "the tile's mounting of it", because in this panel the placeholder is **not**
inside a `<button>` — the detail art is not clickable — so the spec violation does not recur
here.

**Q12 — AS PROPOSED.** A document-level `keydown` releases the pin; the module header states
that **c6-5** registers earlier and calls `stopPropagation`, and that this story cannot test
the layering because no overlay exists yet.

**Q13 — AS PROPOSED.** `alt=""` on the detail art; the `<h2>`-adjacent card-name heading is the
carrier. The divergence from UX-DR48's literal words is stated in the open and goes on the epic
manual-testing checklist for a real screen reader.

**Q14 — AS PROPOSED.** The panel renders **only when `surface.kind === 'deck'`**, which closes
UX validation **L8** in the one direction the contract does specify
(`EXPERIENCE.md:112`, *"Right column panels hidden"*). c4-7 and c4-10 inherit the ruling.

**Q15 — AS PROPOSED.** `[...boards.commander, ...boards.mainboard.flatMap((g) => g.cards)][0]`
— the grid's own visual order, which starts with the commander. Total over both empty boards.
Because `CardGrid.tsx` stays read-only, the expression is necessarily written a second time;
what stops it being a second *rule* is a test that renders `CardGrid` over the same boards and
asserts the resolved target is the id of the **first tile the grid actually draws**.

**One ruling this story owes that no question asked for.** AC 17's refusal — *the unknown-card
variant cannot become the inspection target* — is implemented **in the slice**, not in the
tile: `setHovered` and `togglePin` refuse an id whose cache entry is `unknown` with
`placeholder === 'unknown-card'`. The tile is the wrong home because c4-4's grid never renders
that variant (it draws `named-card` on an image error, and 0 of 2,027 deck rows are dangling),
so a tile-side refusal would be untestable theatre; the population that really has one is Epic
6's thumbnails, and they reach the target through the same two verbs. The consequence is one
new export in `src/state/cards.ts` — `readCardEntry(cardId)`, a plain imperative read —
because `store-writes.test.ts`'s writer scan is a **name-presence** heuristic
(`/\bsetState\b/ && /\buseCardStore\b/`), so importing `useCardStore` into a module that writes
its own store would report `cards.ts` as having two writers. A false-positive guard failure
whose only other repair is weakening the guard is the one this repo refuses.

### Completion Notes List

**The panel is on the glass and the deck responds.** Hover or focus a tile and the right column
updates in place; click pins it; a second click, Esc or the unpin control releases. Verified on a
real engine against the running backend and the 99-card deck — see the eye-check below, which is
where three of this story's claims stopped being arguments.

#### The headline, confirmed end to end

Q1's measurement held at every level. On the live screen, hovering `Clearwater Pathway //
Murkwater Pathway` — one of the six MDFC Pathways in the deck — puts **`Clearwater Pathway` /
`Land` / `{T}: Add {U}.`** in the panel while the tile's caption beneath it still reads the full
`Clearwater Pathway // Murkwater Pathway`. The top-level record for that card carries a blank
`oracle_text` and the degenerate type line, so **every character of type and rules text on that
panel came from `card_faces[0]` and could have come from nowhere else**. That is *"the rest fills
in place"*, doing something real for the 6% of a deck it is actually about.

#### What the eye-check found, and what it settled (Task 7, deferral 1)

Driven through CDP in a real Microsoft Edge against the live backend, 1600×1100, the 99-card deck
active. Six screenshots; every number below is read off the running page.

- **Deferral 1 — `Panel`'s `level="overlay"` appearance — DONE, not assumed.** The first titled
  overlay panel in the app renders correctly: the `--surface-overlay` step, the hairline header
  rule stopping at the `--radius-lg` corner, and the uppercase `--type-label` title. This entry
  has been open since c2-9.
- **The pinned ring, MEASURED:** `rgb(139, 147, 255) 0px 0px 0px 1px` — that is `--accent`
  (`#8b93ff`), **not** `--accent-dim` (`#575fbe`). Q2's correction is on the screen.
- **The live ring, MEASURED:** `rgb(139,147,255) 0 0 0 1px, rgba(139,147,255,0.22) 0 0 20px,
  rgba(0,0,0,0.5) 0 12px 32px` — DESIGN.md's `card-tile.live-ring` composed over `--shadow-rest`,
  exactly. **Exactly one tile carries it** at any moment (`querySelectorAll('.is-live').length`
  → 1), which is Q7's whole argument rendered.
- **The unpin control's hit box, MEASURED: 61 × 30 px.** The story predicted ≥ 24 × 24 from
  arithmetic (14.3px line box + 2 × `--space-2`) and predicted 30.3px tall; the engine says 30.
- **The cold `size=large` paint:** `/api/card-image/{id}?size=large` resolved to
  `complete=true, naturalWidth=672` — a real Scryfall `large` render, at the width the stylesheet
  comment cites. The panel's art is genuinely a second, colder fetch than the grid's.
- **The announcement, MEASURED live:** `Pinned — Kami of Whispered Hopes`, and the panel drops
  `.is-pinned` on Esc.
- **The oracle clamp, PROVEN on the worst input that exists.** `max-height` resolves to
  **294px** with `line-height: 21px` — **exactly fourteen lines**, which is what the `21em`
  derivation claims. The deck's longest real card (`Vraska, Betrayal's Sting`, 452 chars) renders
  in **84px**, so the clamp never fires for a real deck; the corpus's worst card (`Baldur's Gate
  Wilderness`, 1,489 chars) written into the live element measures **scrollHeight 525 vs
  clientHeight 294 → clamped**, with `overflow-y: auto` engaged and the shell's single scroller
  still free of horizontal overflow. Both numbers are recorded because both matter: the clamp is
  inert today and correct for the case it exists for.

**One thing the eye-check disproved before it became a defect report.** Atraxa's cost renders
**four** pips, not five — which looked wrong until it was checked: `Atraxa, Praetors' Voice` is
`{G}{W}{U}{B}`, cmc 4, with no generic symbol at all. The rendered accessible name is
`green, white, blue, black`. Recorded because "the panel is dropping a generic pip" is exactly
the kind of thing that gets filed from a screenshot.

**Two observations, neither a defect, both for the stories that inherit this column.** At a
1100px viewport the panel's TEXT sits below the fold, because a 452px column renders the card art
about 630px tall — the right column scrolls, which is `.app-shell-columns` working as designed,
but **c4-7 and c4-10 stack beneath this panel** and should know the art already spends a
screenful. And oracle text renders Scryfall's raw brace notation (`{T}: Add {U}.`); no artefact
asks for symbol substitution in rules text and c2-8's `ManaCost` parses COSTS rather than prose,
so this is left as it is and declared rather than quietly changed.

#### Decisions taken beyond the fifteen questions

1. **The art state machine moved to `src/containers/useCardArt.ts`.** c4-4 wrote the three states
   and the two halves of the browser-cache race inside `CardTile`, correctly, with one consumer.
   This story is the second, at a different cache key — and this exact fix has **already been
   repaired once** (c4-4's review found the cached-FAILURE arm missing). Two copies would have
   been one copy repaired and one not. The story's own source-tree note anticipated it (*"a
   split-out helper makes it 5"*); it makes it 6.
2. **`CONTAINERS` gained a rule the category did not have: `src/api/` is importable, TYPE-ONLY.**
   The panel must name a wire shape and must not re-declare one (`wire-contract.test.ts` bans
   that outright), so the permitted-roots list was widened — and widening a positive filter that
   reads SPECIFIERS would have let `import { readCard } from '../../api/client'` in as a second
   network door. So the widening ships with the enforcement half: every `src/api/` import from a
   container must be `import type`, and the inline-`type` form is refused because
   `verbatimModuleSyntax` still runs the module. That is `posture.test.ts`'s primitive rule,
   restated for the category that never had it. Probe (e) fires on it.
3. **AC 17's refusal lives in the slice, not the tile** — with `readCardEntry` added to
   `cards.ts` so that `store-writes.test.ts`'s name-presence heuristic is not tripped by a module
   that mentions `useCardStore` while writing its own store. The full argument is in Task 0's
   record; the short version is that the tile has no population to refuse and Epic 6's thumbnails
   do.
4. **The announcement is captured during RENDER, not in an effect.** The first spelling used
   `useEffect(..., [pinnedId])` and `react-hooks/set-state-in-effect` was right to reject it: a
   `setState` in an effect is a second commit, so the pinned ring and the announcement would land
   in different frames. It is now the render-time adjustment React documents — the same pattern
   `useCardArt` uses — which also removes a render pass from every pin.

#### Three pre-existing assertions changed, all strengthened

- `App.test.tsx`'s **"seeds the card cache … at no extra request"** read
  `callsTo('/api/cards/') === 0`, which was honest while nothing consumed the hydration tier.
  This story gives that route its first production caller, so **zero is no longer the property
  worth asserting — one is**, and it is sharper: the summary tier is still free for every card in
  the deck, and hydration costs exactly one request for the one card being looked at.
- **The image count** is now `tiles.length + 1`, with the extra one named (the detail render) and
  a second assertion that exactly one `<img>` carries `size=large`. Spelled as arithmetic rather
  than relaxed to a floor, so a stray second image still fails.
- **`getByRole('banner')` became a scope through the `h1`**, on a MEASURED jsdom fidelity limit:
  HTML-AAM maps `<header>` to `banner` only when it is not inside `article`/`aside`/`main`/`nav`/
  `section`; `aria-query`, which testing-library resolves roles through, maps it
  **unconditionally**. Measured with a two-header probe — a `<header>` inside
  `<section aria-label>` is reported as a second banner in jsdom and as none in a real browser.
  The shipped markup is correct and this suite cannot see that it is. **This is a new blind spot
  for the epic:** every later titled `Panel` inherits it.

#### Evasion probes (AC 38) — 15 planted, 15 caught, 2 negative controls correctly silent

**The probe harness itself was found broken twice, and that is the most useful line here.** Its
first version ran only the guard files each probe targeted, and the **negative control caught
it**: an unmodified tree reported two failures, because `tokens.test.ts` and
`token-usage.test.ts` invoked as a pair outside `npm test` both die with
`TypeError: Cannot read properties of undefined (reading 'config')` before a single assertion
runs. That is the ledgered standalone-runner crash, confirmed — and it is exactly why the story
says *"guards are proven through the full `npm test`, never a standalone file run"*. Every
"CAUGHT" from that harness was the runner. The second break was subtler: invoked with a
lowercase-drive cwd, vitest fails to load `test-setup.ts` and every DOM suite reports
`Failed Suites`. The harness now runs the full suite, refuses to score a run that failed to
LOAD, and carries two do-nothing controls whose silence is what makes the other fifteen mean
anything.

| Probe | Planted | Result |
|---|---|---|
| a | delete `--shadow-pinned-ring` from the token layer | CAUGHT |
| b | "correct" the pinned ring back to `--accent-dim` (the 2.70:1 defect) | CAUGHT |
| c | round the detail ART with a chrome radius (CARD_SHAPED half two) | CAUGHT |
| d | spend `--radius-card` in the CHROME stylesheet (CARD_SHAPED half one) | CAUGHT |
| e | import `readCard` from `src/api/client` into a container (the new type-only rule) | CAUGHT |
| f | ship a fourth store with no `STORES` entry | CAUGHT |
| g | add a trailing period to the pin announcement | CAUGHT |
| h | drop the live-ring class from the tile | CAUGHT |
| i | put `aria-live` back on the panel (the H4/C1 defect returning) | CAUGHT |
| j | resolve the cold open from the mainboard, ignoring the commander | CAUGHT |
| k | clear the hover unconditionally, losing the blur/focus race | CAUGHT |
| l | recompute the announcement from the RENDERED name (re-announces on hydration) | CAUGHT |
| m | read the BACK face instead of the front | CAUGHT |
| n | let an unknown card become the inspection target | CAUGHT |
| o | drop the `size` parameter, sending the panel to the grid's cache key | CAUGHT |
| CTRL ×2 | reword a comment — **must not** be caught | correctly silent |

Probe (l) was **re-run with a second spelling** and is recorded twice on purpose: its first form
referenced a symbol the module does not import, so it would have failed with a `ReferenceError`
rather than by announcing twice. Re-spelled to recompute from the rendered name in the JSX, it
fails exactly one test — the "announces exactly once" one. A probe caught for the wrong reason
proves nothing, and this is the second harness self-correction on the same principle.

#### What this suite cannot carry, declared (AC 37)

1. **Hover, live-ring and pinned-ring APPEARANCE.** jsdom evaluates no CSS.
   `fireEvent.mouseEnter` proves the WIRING; the look is a source claim plus the eye-check above,
   which is why the eye-check measured the two rings' computed values rather than describing them.
2. **The reduced-motion media query.** jsdom does not evaluate media queries into computed style,
   so an assertion there would read the unreduced value and pass for the wrong reason. This story
   ships something stronger than a fallback: **no `transition` and no `animation` in either new
   stylesheet, at any setting** — so the enumerated shipped-motion pin in `token-usage.test.ts`
   needs no edit, and there is nothing for a media query to switch off.
3. **The accessible name as a screen reader phrases it.** `Pinned — {name}` is pinned
   byte-for-byte against the epic and measured in the live DOM; how a real reader handles the em
   dash is the epic manual-testing checklist's. **So is Q13's `alt=""` divergence from UX-DR48's
   literal words** — the panel's name is announced once by construction, and only a real reader
   can confirm it sounds right.
4. **Esc's LAYERING.** UX-DR39 closes an open agent view first, then a pin. No overlay exists
   until c6-5, so there is nothing to layer against and no honest test to write. The contract
   c6-5 relies on — it registers its own handler and calls `stopPropagation()` — is written into
   `CardDetail.tsx`'s header instead.

#### The six inherited deferrals, each dispositioned (AC 36)

1. **`Panel`'s appearance is not dev-verified (`:1343`, `:3450`) — DONE.** Performed, not
   assumed; see the eye-check above. Open since c2-9.
2. **Prices (`:1993-2003`) — CLOSED by absence, deliberately.** There is no price field on the
   wire and Brad ruled at c3-2 Q4 that there should not be a permanently-null one, so this panel
   renders nothing there: no zero, no placeholder, no empty slot. Asserted **at the type**
   (`Extract<keyof Card, 'prices' | 'price'>` must be `never`), which is the only place an
   absence can be asserted, plus a rendered check that no `$` reaches the glass. **The import
   work is NOT raised as a brief**: its cost is already on the record (a new column or side
   table, an importer change, a hand-written migration, a re-import of 38,261 rows, plus a
   staleness story) and nothing in this epic needs it.
3. **The card cache's terminal-after-three asymmetry (`:3372`) — MADE VISIBLE, as promised, and
   re-homed unchanged.** This story is the first thing that spends attempts: a hover sweep now
   calls `hydrateCard` once per distinct card. The fix (`resetCardCache()` on a recovery
   transition) is still **c5-4 / c5-6's** by c4-2's Q7 ruling; what this story owed was to stop
   it being theoretical, and it is not — the seam it runs through is exactly the one `deck.ts`'s
   `subscribeSystemState` recovery re-drive already watches.
4. **The named placeholder's undeclared vertical edge (`:3685-3691`) — DISPOSITIONED (Q10).**
   At detail size the answer is a declared clamp rather than a silent clip: `max-height: 21em`
   (measured: 294px = 14 lines) with `overflow-y: auto`, so a long card scrolls inside its own
   box instead of clipping at both edges. The PLACEHOLDER's own `overflow: hidden` is untouched —
   this story renders it at detail size and did not need to change it, because the clamp is on
   the oracle block rather than on the card box.
5. **`<div>`-in-`<button>` (`:3743-3748`) — NO CHANGE, residue NARROWED (Q11).** In this panel
   the placeholder is not inside a `<button>` at all — the detail art is not clickable — so the
   spec violation does not recur here, and with two consumers in view the honest scope is "the
   tile's mounting of it" rather than "the primitive". Changing the primitive's root for one
   consumer against the other's interest would have been the wrong repair.
6. **The reduced-motion transform guard compares selector text (`:3750`) — NOT TRIGGERED.** This
   story ships no transform and no transition, so it added no registration and the guard's
   enumerated pin is untouched. The residue stands for whoever ships the next motion (c4-6's 3D
   flip, c6-5's bloom).

**And the two that are not homed here but were touched, both confirmed rather than re-opened:**
the standalone-runner crash is confirmed live (it broke this story's own probe harness, above),
and the jsdom accessible-name limit is asserted as membership plus the pinned spelling, with the
phrasing question left where it belongs.

#### The ten gates, and the numbers

| Gate | Result |
|---|---|
| `npm run lint` | green |
| `npm run format:check` | green |
| `npx tsc -b --force` | green (`--force`, not `-b` — the cache hides `TS2835` cascades) |
| `npm test` | **1,165 passed / 47 files** (was 1,086 / 44 at `b26e8f4`) |
| `npm run build` | green |
| `uv run pytest` | **2,501 passed / 1 skipped**, unchanged — **no Python was touched** |
| `ruff check .` | green |
| `ruff format --check .` | green (307 files) |
| `mypy src/` | green (89 files) |
| `mypy src/ --platform win32` | green (89 files) |

**A correction to the story's own baseline, stated rather than smoothed over:** don't-break #16
records the Python suite as *"2,447 passed / 1 skipped / 54 deselected"*. That figure is stale —
c4-4's record measures 2,501 and this run measures 2,501. The invariant (Python is untouched)
holds; the number in the story text did not.

**Tokens: 66 → 68**, both pins moved in the same commit (`expectedNames` + `toHaveLength` in
`tokens.test.ts`, `declaredTokens.size` in `token-usage.test.ts`). Containers: **3 → 6**.
Copy modules: **6 → 7**. Stores: **3 → 4**. Wire aliases gained `CardFace`.

**Bundle, measured against c4-4's baseline and rebuilt:**

| Asset | Baseline (`b26e8f4`) | This story | Δ |
|---|---:|---:|---|
| `index-*.js` | 208,004 B (`index-mnVGJAvJ.js`) | **213,053 B** (`index-DC_majOx.js`) | +5,049 |
| `index-*.css` | 11,579 B (`index-Cgivw4Tq.css`) | **13,431 B** (`index-BkKkxe_n.css`) | +1,852 |

AC 40's prediction confirmed: **the JS bundle had to change and did** — this story mounts a new
component. The CSS changed too, which is the two new stylesheets and the tile's three live-ring
rules. The `plugin/` mirror was regenerated and is **byte-identical file for file** to
`src/companion/app/static/`.

### File List

**New**

- `ui/src/state/inspection.ts`
- `ui/src/state/inspection.test.ts`
- `ui/src/containers/useCardArt.ts`
- `ui/src/containers/CardDetail/CardDetail.tsx`
- `ui/src/containers/CardDetail/CardDetail.test.tsx`
- `ui/src/containers/CardDetail/CardDetail.css`
- `ui/src/containers/CardDetail/CardDetailChrome.css`
- `ui/src/containers/CardDetail/copy.ts`
- `ui/tests/pin-announcement-copy.test.ts`

**Modified**

- `ui/src/App.tsx` — passes `right`, and the Q14 ruling in its header
- `ui/src/App.test.tsx` — three assertions changed, all strengthened; the hydration fixture route
- `ui/src/api/schema.ts` — the `CardFace` alias and the ledger correction
- `ui/src/api/schema.test.ts` — pins `CardFace` in both directions
- `ui/src/state/cards.ts` — adds `readCardEntry`
- `ui/src/containers/CardTile/CardTile.tsx` — five handlers, the live class, the shared art hook
- `ui/src/containers/CardTile/CardTile.test.tsx` — the inspection block, the `size` tests
- `ui/src/containers/CardTile/CardTile.css` — the three live-ring rules
- `ui/src/containers/CardTile/imageUrl.ts` — the `size` parameter and `CardImageSize`
- `ui/src/styles/tokens.css` — `--shadow-live-ring`, `--shadow-pinned-ring`
- `ui/tests/tokens.test.ts` — 66 → 68; the repaired absence test; the pinned-ring test
- `ui/tests/token-usage.test.ts` — `declaredTokens.size` 68; `CARD_SHAPED` gains `CardDetail.css`
- `ui/tests/shell.test.ts` — `CONTAINERS` 3 → 6; the `src/api/` type-only rule and its probe
- `ui/tests/store-writes.test.ts` — `useInspectionStore` in `STORES`
- `ui/tests/copy-rules.test.ts` — `CardDetail/copy.ts` in `COPY_MODULES`
- `_bmad-output/planning-artifacts/ux-designs/…/DESIGN.md` — Q2's amendment (`pinned-ring`
  `accent-dim` → `accent`), in the frontmatter and in the Components prose
- `src/companion/app/static/**` + `plugin/server/src/companion/app/static/**` — rebuilt bundle
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- **2026-08-05 — implemented, status `ready-for-dev` → `review`.** The persistent card detail
  panel: transient hover/focus inspection, click-to-pin, Esc and unpin release, and the first
  user-interaction state in the codebase. All fifteen open questions answered as proposed, with
  three stated deviations (a third field in the slice, one added verb `clearHovered`, and the
  `21em` clamp expressed in `em`) and one ruling the questions did not ask for (AC 17's refusal
  in the slice). Q2's contrast defect fixed in the artefact as well as in the code. Tokens
  66 → 68, containers 3 → 6, stores 3 → 4, copy modules 6 → 7. Frontend suite 1,086 → 1,165;
  Python 2,501 / 1 skipped, untouched. Fifteen evasion probes, fifteen caught, two negative
  controls silent — after the probe harness was itself found broken twice. Six inherited
  deferrals dispositioned, one of them (`Panel`'s overlay eye-check, open since c2-9) closed by
  a real browser. Ten gates green; bundle rebuilt and mirrored.

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

2026-08-05: CODE-REVIEWED -> done — three-layer review, 26 raw findings -> 3 decisions + 13 patches applied, 1 deferral, 9 dismissed; auditor confirmed 38/41 ACs on first pass. THE PANEL'S CORE CONTENT RENDERED WRONG FOR MOST OF THE CORPUS: no white-space:pre-line on the oracle block, so newline-separated abilities ran together as one sentence (the eye-check measured the clamp but never looked at a paragraph break); fixed with a source pin holding pre-line in the same rule as the clamp. BOTH HUNTERS INDEPENDENTLY FOUND THE DECK-TRANSITION HOLE: hover and pin survive a live deck replacement (FR-22 is real), so a pin from deck A outranked deck B's cold-open target and the panel rendered a card not on the glass — ruled: clear both in the boards effect via a new module-scope deck memory (CardDetail/deckMemory.ts, CONTAINERS 6 -> 7), same-deck remount still preserves the pin (FR-17 intact, both directions tested). THE WRITTEN c6-5 ESC CONTRACT HAD A HOLE: an element-scoped stopPropagation cannot pre-empt a document-level listener when focus sits outside the overlay subtree — contract rewritten in both module headers to document-capture-phase, and the handler now ignores isComposing/defaultPrevented. TWO TASKS WERE MARKED COMPLETE WITHOUT THEIR TESTS (AC 6's c4-5 displacement assertion, AC 9a's no-detail-panel-during-state-panel test — both written now) and Q3's promised Tab-stop record existed only in a test comment claiming it was in the module header (now it is). Also: unpin now hands focus to the panel <h2> (activation was dropping focus to <body>), a pin of a name-less cache entry announces late-but-once instead of never (AC 23's exactly-once could silently become zero), the failed-art placeholder moved inside the art box (it had lost --shadow-rest), the type-only probe now fires against the guard's own regex rather than a private copy, and the MDFC combined-vs-face announcement name is a declared divergence on the manual checklist. DEFERRED to c4-11: the 21em oracle scroller is keyboard-unreachable (the fix adds a Tab stop UX-DR40 doesn't enumerate AND breaks AC 25's [tabindex]-absence test — both that story's to renegotiate). 1,165 -> 1,174 frontend / 47 files green, tsc + eslint + stylelint green; bundle JS 213,053 -> 213,482 B, CSS 13,431 -> 13,452 B, mirror byte-identical. Next: commit + PR into feat/companion-c4.

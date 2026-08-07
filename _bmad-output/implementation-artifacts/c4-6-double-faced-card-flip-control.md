---
epic: c4
story: c4-6
work_branch: feat/companion-c4
story_branch: feat/companion-c4-6-dfc-flip-control
depends_on: >-
  c4-5 (merged at `bd72fc0`, PR #44) — the inspection slice, `CardDetail`, and the `fromCard`
  face-first read whose hard-coded `card_faces?.[0]` this story turns into a choice; `CardTile`'s
  handlers are on its `<button>` **specifically** so this story's control can `stopPropagation()`
  out of them, and `CardTile.test.tsx:430` already ships a test proving that contract in advance.
  c4-4 (merged at `b26e8f4`) — `CardTile`, `useCardArt`, the quantity badge that owns the tile's
  top-RIGHT and reserves the top-LEFT for this story by name, and `src/containers/` as the category
  a component that behaves lands in. c4-3 (merged at `b47f603`) — `.card-shape`, and
  `CardPlaceholder` on the failed-art path. c4-1 (merged at `2095050`) — `hydrateCard`, which is
  the **only** source of `card_faces` in the SPA and therefore the sequencing constraint this whole
  story turns on. Also **c3-5** (`GET /api/card-image/...?face=`, whose parameter this story is the
  first and only caller of, and whose `resolve_face_images` is the rule this story must mirror
  rather than re-invent), **c3-2** (`GET /api/cards/{card_id}`, the hydration route), **c2-7**
  (`Panel`), **c2-4** (the token layer, 68 tokens, both pins).
baseline_commit: bd72fc0
---

# Story C4.6: Double-faced card flip control

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad running double-faced cards,
I want a control that flips a card to its back without opening anything,
so that inspecting a card and flipping it are two obviously different actions.

**What this story really is.** The epic calls it *"the densest single component in the feature — it
was the UX gate's H2 and carries a dozen distinct rules"* (`epics-companion-app.md:794`). That is
true, and it is not the hard part. The hard parts are two structural facts that no artefact
mentions and that four previous stories have quietly deferred into this one:

1. **The tile cannot currently know whether it has a back face.** `CardTileProps` is five plain
   values and `CardGrid` subscribes to nothing. `card_faces` exists **only** on the hydrated
   `Card`, and the only thing in the app that hydrates is c4-5's detail panel, on the one card
   being looked at. AC 1 says the control appears *"when its tile renders"* — so either something
   hydrates the deck, or the control cannot exist at render time and UX-DR40's *"immediately after
   its own tile"* Tab stop appears and disappears under a keyboard user. This is Q1, and it is the
   question the whole story is blocked on.

2. **The control is a `<button>` and the tile it sits on is also a `<button>`.** Every shipped
   comment that reserved this slot — `CardTile.tsx:86`, `:266`, `:317`, `inspection.ts:43` — says
   the flip control *"sits INSIDE this button"*, and that containment is load-bearing for a reason
   nobody wrote down: `mouseenter`/`mouseleave` do not fire between an element and its
   **descendants**, so a control inside the button never reads as leaving the tile. But
   `<button>`'s content model bans interactive descendants outright, and React's DOM-nesting
   validator carries a `button`-in-`button` case. The seam that was designed for this story is the
   one thing this story may not build as designed. This is Q2.

Everything else — the material, the glyph, the 3D rotation, the state store, the Tab order — is
specified and tractable. These two are not, and they are why Task 0 exists.

Two more things open here:

3. **This story is the first inline `<svg>` in `ui/src`.** There is no icon system, no viewBox
   convention, no stroke-width, and two shipped components assert the *absence* of SVG in their own
   subtree (`StatePanel.test.tsx:61`, `CardPlaceholder.test.tsx:81`). DESIGN.md asks for *"a
   stroke-based two-arrow rotate glyph … a plain UI glyph, never anything that could read as a mana
   or set symbol"* and gives nothing else. The design system's only iconography note proposes a CDN
   set, which `DESIGN.md:418` bans by name (Q6).

4. **This story ships the first `transform` since c4-4, and it is a 3D one.** `tokens.css:274`
   already reserves the row — `DFC flip 3D Y-rotation -> instant face swap (c4-6)` — and c4-4's
   review hardened the guard to compare **selector text per property**. The ledger residue at
   `deferred-work.md:3750` says in as many words that it *"stands for whoever ships the next motion
   (c4-6's 3D flip)"*. That is now.

## Dev Notes

### The seam that already exists (do not rebuild any of it)

Everything below is **shipped and green at `bd72fc0`**. Read it before writing anything.

**The URL builder is one function and this story adds its second parameter.**
`src/containers/CardTile/imageUrl.ts:81`:

```ts
export const cardImageUrl = (cardId: string, size?: CardImageSize): string => {
  const path = `/api/card-image/${encodeURIComponent(cardId)}`
  return size === undefined ? path : `${path}?size=${size}`
}
```

Its header instructs this story by name (`:59-63`): *"**ONE FUNCTION, NOT A SECOND TEMPLATE
STRING** … **c4-6 adds `face` here**, beside `size`, and inherits the encoding below for free."*
And `:44-51` carries the rule that decides how: **the URL is the browser's cache key**, so an
omitted parameter and its spelled default are two cache entries for one picture. `face=0` must stay
**unspelled**, exactly as `size=normal` is — the front-face grid URL emitted today must come out
byte-identical, and `CardTile.test.tsx`'s "contains no `size=`" assertion must still pass.

**The backend is finished. This is a `ui/`-only story.** `GET /api/card-image/{scryfall_id}`
already publishes `face: integer, minimum 0, default 0` and already resolves it
(`src/companion/app/images.py:463`, `resolve_face_images`). Read that function's rule and mirror
it; do not invent a second one:

```python
faces = list(card_faces or ())
per_face = [dict(face.image_uris) for face in faces if face.image_uris]
if per_face:
    return per_face
return [dict(image_uris)] if image_uris else []
```

Three consequences that are not obvious and are all tested Python-side:

- **`face` indexes the images a card HAS, not its `card_faces` array.** A split or adventure card
  has two faces and **one** image, so `face=1` on it is `404 no_image_data` — *out of range*, not
  "the other half" (`cards.py:245-250`, `test_routes_card_image.py:146`).
- **The discriminator is truthiness of per-face `image_uris`, never key presence and never a layout
  string.** `CardFace` serialises `"image_uris": null` on an unimaged face, so `'image_uris' in
  face` is the wrong test. The Python gate for the identical mistake is
  `test_routes_cards.py:253`'s `any(face["image_uris"] for face in body["card_faces"] or [])`.
- **There is no `layout` anywhere.** The `cards` table has 23 columns and none of them is `layout`
  (`images.py:469`); `Card` has no such field; only 66 of 6,455 stored face objects carry one
  inside `CardFace`'s `extra="allow"` bag, and `test_images.py:156` explicitly proves the resolver
  ignores it. AD-11 is the rule; FR-04's PRD text still says "layout" and is a **PRD amendment
  owed** (`epics-companion-app.md:323`), not a licence.

**The detail panel is already face-specific; this story makes the face a choice.**
`CardDetail.tsx:186`:

```ts
const face: CardFace | undefined = card.card_faces?.[0]
return {
  name: given(face?.name) ?? given(card.name),
  cost: given(face?.mana_cost) ?? given(card.mana_cost),
  typeLine: given(face?.type_line) ?? given(card.type_line),
  oracleText: given(face?.oracle_text) ?? given(card.oracle_text),
}
```

Note it is a **per-field** fallback, not a per-record one, and its docstring (`:168-184`) says
*"c4-6 makes the choice of face a control; this story establishes that the panel is face-specific
at all."* The panel's art is `cardImageUrl(targetId, 'large')` at `:416`, inside
`<div className="card-shape card-detail-art">` — the box DESIGN.md pins the panel's own copy of the
control to.

**The tile's handlers are on the button, deliberately, and a test already proves the opt-out.**
`CardTile.tsx:266-274`:

> ON THE BUTTON, DELIBERATELY: `click` bubbles, so c4-6's flip control suppresses the pin from
> inside this element with `stopPropagation()` and no edit here, while `mouseenter`/`mouseleave` do
> not bubble at all, so moving the pointer onto that control never reads as leaving the tile.

and `CardTile.test.tsx:430` ships `it('lets a CHILD control opt out with stopPropagation — c4-6's
flip, proven early')`. **Read that test before Q2**: it asserts the *behaviour* (a child's
`stopPropagation` suppresses the pin), which stays true under either DOM shape — but the
`mouseenter` half of the sentence above is true **only** while the control is a descendant.

**The material's other half is shipped and is the template.** `QuantityBadge.css:29-58` is
`components.quantity-badge` verbatim, and its header is addressed to this story:

> DESIGN.md gives `components.quantity-badge` and `components.dfc-flip` the same scrim, the same
> blur and the same border "so the pair reads as one family". c4-6 builds the second half of that
> pair, pinned to the tile's TOP-LEFT … This file owns the right corner and nothing else.

It is also the **worked precedent for the stylesheet split**: `CardTile.css` is in
`token-usage.test.ts`'s `CARD_SHAPED` allowlist, whose second half bans a chrome radius in a
card-shaped file — and `dfc-flip.radius` is `{rounded.pill}`. So the control's chrome cannot live
in `CardTile.css` or `CardDetail.css`. A separate, **non**-card-shaped stylesheet is not a
preference; it is the only legal home.

**`useCardArt` keys on `cardId` alone, and that is a defect the moment a face changes.**
`useCardArt.ts:110`:

```ts
if (artFor !== cardId) { setArtFor(cardId); setState('loading') }
```

A flip changes the `<img src>` but not the `cardId`, so the hook does **not** re-arm. Since
`?face=1` is a distinct browser cache key the first flip is always a cold fetch, which means the
tile would sit on the old face with no well and then swap; worse, a tile whose front art already
`failed` renders `CardPlaceholder` **instead of** the `<img>`, so there is no element for a flip to
change. Both consumers (tile and panel) share this hook. See Q7.

**The reduced-motion row is already reserved.** `tokens.css:274`:

```
DFC flip 3D Y-rotation              -> instant face swap                       (c4-6)
```

and the block's header says *"Any motion that cannot be switched off by a duration alone — a
transform, a 3D rotation, a crossfade — adds its own declaration HERE, in this block, in the story
that builds it. A motion with no registered fallback is an incomplete story."* The guard compares
**selector text, per property**, and requires `!important` (c4-4's review hardened both halves; a
no-`!important` registration is a measured cascade no-op).

**`CardFace` is already typed, in both languages.** c3-5 shipped the Pydantic model with
`extra="allow"`; c4-5 added the TypeScript alias (`schema.ts:151`) — a ledger correction that story
stated in the open. `schema.ts:147` reserves the last unread field for this story: *"`image_uris`
is here for completeness and **c4-6's** flip control; nothing in c4-5 reads it."*

### What the real data says (measured at `bd72fc0`, read-only, against the shipped database)

Measured with `sqlite3` in `mode=ro` against `src.paths.data_dir()/cards.db` — 38,261 cards, 40
decks, 2,027 deck rows. **Re-verify these in Task 0 before relying on any of them.**

> Reading gotcha for whoever re-measures: the `card_faces` column holds the literal JSON text
> `'null'` for single-faced rows (SQLAlchemy `JSON` serialises Python `None`), so
> `card_faces IS NOT NULL` selects the whole corpus. Filter `card_faces NOT IN ('', 'null')`. The
> wire is unaffected — `Card.card_faces` deserialises to `null` correctly.

**Who gets a control, and who does not — the four shapes, exhaustive:**

| Shape | Rows | Meaning | Flip control? |
|---|---:|---|---|
| A — top-level `image_uris`, no `card_faces` | 35,036 | ordinary single-faced card | no |
| B — top-level `image_uris` **+** faces with **no** images | **368** | split / adventure / Omen — halves share one artwork | **no** (AC 2) |
| C — `image_uris` null, **every** face carries its own map | **2,778** | transform / MDFC / reversible | **yes** (AC 1) |
| D — `image_uris` null, faces present, images nowhere | 79 | the named-placeholder population | no |
| — neither field | 0 | does not exist | — |

**0 rows carry both**, and **0 rows are partially imaged** (a card's faces either all carry images
or none do). Every one of the 5,556 per-face `image_uris` maps carries all six size keys, so
`size=large` always resolves for a face that exists.

**The finding that corrects the ledger.** `deferred-work.md:2032` warns that *"a `[front, back]`
destructuring is wrong for three real cards"*, citing the face-count histogram **2 → 3,222 · 3 → 2
· 5 → 1**. The histogram is right and the conclusion does not apply here: **all three of those
cards are shape B and get no control.** They are named, so this is checkable rather than
reassuring: `Smelt // Herd // Saw`, `There // They're // Their`, and
`Who // What // When // Where // Why` — three split cards, one shared artwork each. **Every one of
the 2,778 cards that gets a flip control has exactly two imaged faces.** The route's `face` is
still an unbounded integer and its Python tests still prove five faces serve five images (against a
*synthetic* fixture), so the index is the honest spelling — but a two-state toggle is not wrong for
any printing that exists. Q3 rules on which to write.

**The second finding, which will otherwise be filed as a bug from a screenshot.** Of the 2,778
cards that get a control, **2,166 are reversible art printings** — the back face's `type_line` is
literally `Card`, its `oracle_text` is blank, and its `name` repeats the front's. Flipping one is
*correct*: it shows a second piece of artwork for the same card. Only **612** are true
transform/MDFC cards with a different card on the back. **Zero reversible printings appear in any
of the 40 real decks**, so the population Brad will ever see is the 612 — but a reviewer eye-checking
against the corpus will meet the 2,166 first.

**Face records are not uniformly populated.** Across the 6,455 stored face objects: `name`,
`mana_cost` and `oracle_text` are present on all of them; `type_line` on 6,445; `image_uris` on
5,556. **Ten cards that DO get a flip control have a face with a null `type_line`** — the Un-set
"(cont'd)" minigame cards, e.g. `Roll for Initiative // Roll for Initiative (cont'd)`. That is the
population `fromCard`'s per-field `??` fallback already exists for; do not replace it with a
per-record one.

**The back face can be the longest text in the panel.** The longest back-face `oracle_text` in the
corpus is **1,232 characters** (`Magic and Minions // Magic and Minions (cont'd)`). c4-5's oracle
block clamps at `max-height: 21em` — measured live at **294px / fourteen lines** — with
`overflow-y: auto`. The clamp is inert for every front face in a real deck (worst: 452 chars) and
**fires on a back face**. It is also the block c4-11 owns a keyboard-reachability deferral on.

**In the live decks — where AC 1 and AC 2 can be seen on one screen:**

- **2,027 deck rows across 40 decks; 42 rows get a control; 20 of the 40 decks contain at least
  one.**
- `Atraxa Counter Cabinet v2 (owned)` (99 rows, the deck every C4 story is eye-checked against):
  **6**, all MDFC Pathways, all `Land` back faces with a one-line `{T}: Add {X}.`
- **`Prismatic Dragon` (38 rows) is the eye-check deck this story wants**: **1 with** a control
  (`Marang River Regent // Coil and Catch`) and **9 without** (Tarkir Omen dragons —
  `Creature — Dragon // Sorcery — Omen`, shape B). Both acceptance criteria, one screen, real data.
- `Ayara Black Devotion` (69 rows): **3 with** (`Tergrid, God of Fright // Tergrid's Lantern`,
  `Graveyard Trespasser // Graveyard Glutton`, `Agadeem's Awakening // Agadeem, the Undercrypt`)
  and **3 without** (two Adventures + `Emeritus of Woe // Demonic Tutor`).
- `Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel` appears in three decks and is the
  richest back face available — a `Legendary Creature — Angel Nightmare Avatar` with real rules
  text, so the panel's face-swap is visible in every field at once.

**The cheap predicate, measured and rejected — record it rather than re-derive it.** `' // '` in
`CardSummary.name` selects **3,194** of the 3,225 faced cards and only **65** of the 2,027 deck
rows (worst deck: 10), which would make Q1's hydration sweep ~15× smaller. It **misses 31 faced
cards** — the reversible printings whose duplicated name the importer dedupes
(`Anje Falkenrath`, `Reckoner Bankbuster`, `Tuvasa the Sunlit`, …). Zero of those 31 are in a live
deck today, so the predicate is presently perfect and structurally wrong. It is written down here
so the decision is a decision.

### The wire types — what this story may and may not read

Import from `src/api/schema.ts` (the sanctioned barrel). **Never** import `./types` outside
`src/api/`, and never re-declare a wire shape (`tests/wire-contract.test.ts`).

`CardSummary` (free, seeded for every deck card by `seedCardSummaries`) — **carries no
`card_faces` and no `image_uris` at all**:
`id`, `name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `rarity`, `set_code`.

`Card` (hydrated) adds, among others: **`card_faces?: CardFace[] | null`**,
`image_uris?: { [key: string]: string } | null`.

`CardFace` — every named field optional **and** nullable, plus an open index signature:

```ts
CardFace: {
  name?: string | null
  mana_cost?: string | null
  type_line?: string | null
  oracle_text?: string | null
  image_uris?: { [key: string]: string } | null
} & { [key: string]: unknown }
```

**Do not read `image_uris` to build a URL.** `tests/no-scryfall-hosts.test.ts` bans the Scryfall
host family across all of `src/`; art goes through `cardImageUrl` (AD-11). This story reads
`face.image_uris` **only as a boolean** — is this face imaged — which is exactly what
`resolve_face_images` does with it.

### Decide-once rulings this story inherits (do not re-derive)

1. **`src/containers/` is where a component that BEHAVES lives** (c4-4 Q1). `src/components/` is a
   closed set-equality category (`shell.test.ts:1268`, `PRIMITIVES` length 17) whose members are
   banned from hooks, `on*` in either position, `ref` in either position, spread, and a value
   `react` import. A flip control needs handlers; it is a container.
2. **The `CONTAINERS` guard is git-derived set equality with an exhaustive import list**
   (`shell.test.ts:1457`), plus a non-vacuity pin `expect(CONTAINERS).toHaveLength(7)` at `:1614`
   that moves in the same commit. CSS side-effect imports and `'react'` are listed.
3. **`src/api/` is importable from a container, TYPE-ONLY** (c4-5's second decision). Every
   `src/api/` import from a container must be `import type` — not the inline-`type` form, because
   `verbatimModuleSyntax` still runs the module. Widening a specifier filter without the
   enforcement half would let `src/api/client.ts` in as a second network door.
4. **UX-DR4 card-radius exclusivity is a gate in both directions.** `.card-shape` in
   `src/styles/card-geometry.css` is the ONE declaration — consume it by class name, never import
   it, never re-declare `aspect-ratio` or `border-radius`. A card-shaped stylesheet joins
   `CARD_SHAPED` **with its reason** and thereby also accepts the converse: no `--radius-sm/md/lg/pill`
   in that file. `CardTile.css`/`QuantityBadge.css` and `CardDetail.css`/`CardDetailChrome.css` are
   the two shipped precedents; this story's pill-radius control is the third instance of the same
   collision.
5. **Every shadow and radius goes through a token; composites live in the layer.** A composite
   `box-shadow` cannot be written in a component stylesheet at all — stylelint's
   `declaration-property-value-allowed-list` restricts `box-shadow` to `none` or a comma-list of
   `var(--shadow-*)` / `var(--glow)`.
6. **The reduced-motion registration is a derived gate, not prose** — see above. It compares
   selector **text**, per property, and requires `none !important`.
7. **Nothing pulses, loops or alternates, at any setting.**
8. **`:focus-visible`, never `:focus`; `outline: none` is banned in all four spellings.**
9. **`--accent-dim` on `--surface-overlay` is banned** (2.70:1). The guard is same-block only.
10. **Emptiness is `filled()` / `typeof` + `trim()`, never truthiness; a number is
    `Number.isFinite`, never `count &&`.** `given()` is the shared string-narrowing spelling and
    returns the **trimmed** value; three verbatim copies exist and the third was ratified at c4-5
    review at its own recorded threshold.
11. **`px` literals in `src/containers/` need a DESIGN.md citation within a sentence of the value**
    (`shell.test.ts:975`). `28px`, `32px` and `blur(6px)` all qualify; `--space-2` **is** 8px, so
    "inside 8px" is a token rather than a literal.
12. **A card refusal never puts a panel on the glass** (c4-1 AC 13, FR-13). `panelFor()` is not
    called on the card path; nothing switches on `entry.reason`.
13. **The order the view draws is the store's, not a second sort** (AD-12).
14. **`AppShell.tsx` is never edited; placeholders are displaced, not deleted** (c2-9).
15. **A flip is not an inspection.** Stated twice in shipped source (`inspection.ts:43-54`,
    `CardTile.tsx:86-92`): the control touches **none** of `setHovered` / `clearHovered` /
    `setFocused` / `clearFocused` / `togglePin` / `clearPin`.
16. **Any authored user-facing string lives in a `copy.ts` beside its component** and is registered
    in `COPY_MODULES` (`tests/copy-rules.test.ts:103`, seven entries today), which gates voice over
    `alt`, `title`, `aria-label` and seven other attributes. **Card data is not copy.**

### Latest technical specifics

**React `^19.2.8`.** React's DOM-nesting validator carries a `button`-in-`button` case and is
expected to warn (React 19's wording: *"In HTML, `<button>` cannot be a descendant of `<button>`.
This will cause a hydration error."*). **Verify this empirically in Task 0 rather than assuming
it** — the answer decides Q2, and a warning React emits only in development is a different fact
from one it emits always. Note that React builds the DOM imperatively, so unlike a parsed HTML
document the nesting *does* survive into the tree; the question is validity and AT behaviour, not
whether the element exists.

**zustand `^5.0.14`.** v5 removed `create`'s equality argument and matches React's default
referential comparison, so a selector returning a **new object or array on every call** re-renders
forever. Every shipped selector in `src/state/` returns a primitive or a stored reference. A
`useFaceIndex(cardId): number` returning a number is correct by construction; a
`useFlippableFaces(cardId): CardFace[]` returning a filtered array is the mistake this paragraph
exists to prevent — derive the **count**, not the array, or memoise against the stored entry.

**CSS 3D.** `transform-style: preserve-3d` and `backface-visibility: hidden` are not motion and are
not neutralised by the reduced-motion block; only `transform` itself is. `perspective` belongs on
the parent of the rotating element. jsdom evaluates none of it — see the declared-limits section.

**vitest 4, two projects.** `node` (`ui/tests/**`, guards, `nodenext`) and `dom`
(`ui/src/**/*.test.{ts,tsx}`, jsdom, `src/test-setup.ts`). Globals are off; `cleanup` is registered
manually. `fireEvent` is the suite's only DOM-event idiom — there is no `userEvent` and
`tests/package-contract.test.ts` pins the dependency list, so adding one is a decision with a diff.

### The seventeen things this story must not break

1. **The grid's front-face URL is byte-identical.** `cardImageUrl(cardId)` with no arguments must
   still emit `/api/card-image/{id}` with **no query string**, and `CardTile.test.tsx`'s "contains
   no `size=`" assertion must pass unmodified. A spelled `face=0` is a second cache key for the
   warm picture.
2. **`AppShell.tsx` — not edited.** `AppShell.test.tsx` passes unchanged.
3. **`CardTile`'s accessible name — exactly once**, `Black Lotus ×4` spelling pinned by c4-4's
   review (`aria-labelledby` ID order, **with a space**). A new control inside or beside the button
   must not join that name.
4. **`CardGrid`'s visual order and its `boards`-only prop** — no second flattening, no re-sort.
5. **`useCardEntry`'s "starts nothing" contract** — do not add an effect or a fetch to it.
6. **`hydrateCard`'s attempt cap (`MAX_ATTEMPTS_PER_CARD = 3`), in-flight dedupe and never-rejects
   posture.**
7. **The inspection slice's five values and eleven verbs** — this story reads none of them and
   writes none of them. `useIsLiveTarget`'s boolean-primitive contract is untouched.
8. **`Panel` is a primitive a consumer may not restyle**; it is `overflow: hidden` with 12px body
   padding.
9. **`.app-shell-columns` is the app's single scroll container**; `shell.test.ts` bans
   `overflow: hidden|clip` on the roots and that scroller, and exempts only `CardDetail`'s panel.
10. **The one network door stays `['src/api/client.ts']`** (`posture.test.ts:339`). An `<img src>`
    is the browser's request, not the app's.
11. **`store-writes.test.ts`'s `STORES` table** — four entries today; a new slice is registered
    with `store`/`owner`/`why`, and **no component calls `setState`**. The guard's writer scan is a
    name-presence heuristic (`/\bsetState\b/ && /\buseCardStore\b/`), which is why `readCardEntry`
    exists — do not import `useCardStore` into a module that writes its own store.
12. **`tests/wire-contract.test.ts`** — no re-declared wire shape outside `src/api/`.
13. **The 68-token inventory and its two pins** (`expectedNames` + `toHaveLength` in
    `tokens.test.ts:239,306`; `declaredTokens.size` in `token-usage.test.ts:1086`). This story is
    expected to add **none** — `dfc-flip`'s whole material resolves to existing tokens, exactly as
    `quantity-badge`'s does. If a token is added, both pins move in the same commit and the story
    says why.
14. **`CARD_SHAPED`'s four entries and both directions.**
15. **The reduced-motion registration block — extended, never bypassed**, and the enumerated
    shipped-motion pin (`token-usage.test.ts:2305` — *"the story that added or removed a motion
    updates this pin"*) moves in the same commit.
16. **`tests/copy-rules.test.ts`** — any authored string lives in a `copy.ts` and is registered.
17. **Python is untouched.** `uv run pytest` must stay at **2,501 passed / 1 skipped**. The
    backend's `face` parameter, its resolver and its eleven face tests are complete; there is
    nothing to add.

### Source tree — what exists, what this story touches

```
ui/src/
  api/schema.ts                             READ ONLY — `CardFace` already exported (c4-5)
  state/
    cards.ts        useCardEntry, hydrateCard, readCardEntry   READ ONLY unless Q1 says otherwise
    deck.ts         useDeckState, surfaceOf, Surface           MODIFY? — Q1's sweep owner
    faces.ts                                NEW     — the flip-state slice (Q4)
    faces.test.ts                           NEW
  containers/
    useCardArt.ts                           MODIFY  — a face-aware key (Q7)
    FlipControl/FlipControl.tsx             NEW     — the control, mounted twice (Q5)
    FlipControl/FlipControl.test.tsx        NEW
    FlipControl/FlipControl.css             NEW     — chrome; NOT in CARD_SHAPED
    FlipControl/copy.ts                     NEW     — the accessible name (Q6)
    CardTile/CardTile.tsx                   MODIFY  — mount the control, the `face` on the img (Q2)
    CardTile/CardTile.test.tsx              MODIFY
    CardTile/CardTile.css                   MODIFY  — the flip motion (Q10)
    CardTile/imageUrl.ts                    MODIFY  — the `face` parameter
    CardDetail/CardDetail.tsx               MODIFY  — face-indexed `fromCard`; the second mount
    CardDetail/CardDetail.test.tsx          MODIFY
    CardDetail/CardDetailChrome.css         MODIFY? — the panel-side flip motion
    CardGrid/CardGrid.tsx                   READ ONLY unless Q2 says otherwise
  styles/tokens.css                         MODIFY  — the reserved reduced-motion row
ui/tests/
  shell.test.ts        CONTAINERS + toHaveLength(7 → 8+)       MODIFY
  store-writes.test.ts STORES 4 → 5                            MODIFY
  copy-rules.test.ts   COPY_MODULES 7 → 8                      MODIFY
  token-usage.test.ts  the enumerated shipped-motion pin       MODIFY
  tokens.test.ts       ONLY if a token is added — expected not to be
```

### The inherited deferrals — give each a disposition (AC 32)

C2 retro ruling **R2**: inherited deferrals are acceptance criteria at context time, and "not
mentioned" is a failure of the AC. Six are homed on this story by name or by trigger; the line each
lives on in `deferred-work.md` is given so this is checkable.

1. **`card_faces` crosses the wire untyped (`:2027-2034`) — Home: c4-6, explicitly.** Half of it
   is already closed: c3-5 shipped the `CardFace` Pydantic model and c4-5 added the TS alias. What
   remains is the entry's *conclusion* — *"a `[front, back]` destructuring is wrong for three real
   cards"* — which this story's measurement **corrects**: all three are shape B and get no control.
   The disposition owed is a correction on the record, not a fix.

2. **The `'Card // Card'` printing cannot be grouped correctly from the deck payload
   (`:3515-3520`) — Home: c4-6.** *"Fixing it means 99 extra card fetches for a case no deck
   contains. Home: c4-6, which adds `CardFace` and renders faces anyway; if it lands, the grouping
   can read the front face properly for the ids already hydrated."* Q1 decides whether those 99
   fetches happen for an unrelated reason — if they do, this entry becomes free. 2,274 corpus rows,
   **0 in any live deck**.

3. **The reduced-motion transform guard compares selector text (`:3750`)** — *"the residue stands
   for whoever ships the next motion (c4-6's 3D flip)."* **Triggered here.** False failure, not
   false pass; the repair is to write the matching selector.

4. **`CardPlaceholder` renders a `<div>` and `<button>` takes phrasing content only
   (`:3743-3748`)** — narrowed by c4-5 from "the primitive" to "the tile's mounting of it". Q2 is
   the same seam one level worse (an *interactive* descendant, not merely a flow one), so this
   entry is re-decided here whether or not it is re-homed.

5. **The `images.py` split decision (`:2989-2997`) — Home: the C4 retrospective**, *"with c4-6
   still to add the flip control"*. This story is the first caller of the `face` parameter and the
   first to spend the disk cache at a non-zero face key, so the evidence it feeds forward is
   whether the pacer, the disk cache and the negative cache need anything at `face=1`.

6. **The 21em oracle scroller is keyboard-unreachable (`:3778-3786`) — Home: c4-11.** Not this
   story's to fix, but this story is the first that can make the clamp **fire** in a real deck, via
   a 1,232-character back face. Say so; do not fix it.

Three more are not homed here but will be touched: the **standalone `token-usage.test.ts` runner
crash** (prove guards through the full `npm test`, never a single-file run), the **jsdom
accessible-name spelling limit**, and c4-5's new epic blind spot — **`aria-query` maps `<header>`
to `banner` unconditionally**, so any test scoping by role near a titled `Panel` inherits it.

### Open questions — answer these before writing code

**Q1. How does a tile learn it has a back face? — proposal: hydrate the deck's distinct card ids
once, after boot, owned by the deck slice.**
`CardSummary` carries neither `card_faces` nor `image_uris`, and only `hydrateCard` produces them.
Options: **(a)** a boot-time sweep calling `hydrateCard` for every distinct id in the loaded deck;
**(b)** add a derived field to the wire (e.g. an image-face count on `CardSummary`), computed by
`resolve_face_images` so there is still one rule; **(c)** render the control lazily, only once a
card happens to be hydrated by an inspection.
**(c) fails AC 1's literal words** (*"when its tile renders"*) and creates a real keyboard defect:
the Tab stop UX-DR40 places *"immediately after its own tile"* would materialise mid-traverse.
**(b) is the architecturally cleanest and the most expensive**: `CardSummary` lives in
`src/data/schemas/card.py` and is consumed by `card_search.py`, `deck_import.py` and
`deck_management.py`, so it is an MCP-visible schema change plus an `openapi.json` regeneration,
the committed-schema pins, the generated `types.d.ts` and both plugin mirrors. **Proposal: (a)** —
no wire change, no MCP blast radius, bounded (≤99 distinct ids per deck; `hydrateCard` dedupes
in-flight and caps at three attempts), and it closes inherited deferral 2 for free. Cost to measure
in Task 0 and state against NFR-05: the sweep is after-paint work — the grid renders from the
summary tier and does not wait for it — but it competes with ~99 image fetches for the browser's
connection pool. The cheaper `' // '`-name filter is measured above and **rejected**: it is wrong
for 31 corpus cards and right only by accident today.

**Q2. Inside the tile's `<button>` or beside it? — proposal: beside it, in a positioned wrapper,
with the pointer handlers moved to the wrapper.**
Four shipped comments assume "inside". `<button>`'s content model bans interactive descendants and
React is expected to warn. But containment is what makes `mouseenter`/`mouseleave` not fire when
the pointer moves onto the control — so simply moving the control out, unchanged, would make
hovering the flip control **clear the tile's own hover target**, which is a visible defect on the
exact gesture the control exists for.
**Proposal:** `CardTile` renders a new positioning wrapper (`<div className="card-tile-frame">`)
holding the `<button>` and the control as **siblings**; `onMouseEnter` / `onMouseLeave` move from
the button to the wrapper (they cover both children and still do not bubble in from outside);
`onFocus` / `onBlur` / `onClick` **stay on the button**. The button keeps `card-shape`, its own
`--shadow-rest`, `overflow: hidden` and the authored focus outline, so c4-4's eye-check ruling
(*"the button IS the card"*) is preserved intact. The control still calls `stopPropagation()` — now
for the keyboard-activated `click` that would otherwise reach nothing, and as the contract
`CardTile.test.tsx:430` asserts. **State the consequence:** that test's premise changes from
"descendant" to "sibling" and it must be re-proven, not re-worded. The alternative — accept the
nested button — must be argued from a **measured** React 19 behaviour and a screen-reader read, not
from the comments that reserved it.

**Q3. Boolean toggle or face index? — proposal: an index, cycled modulo the imaged-face count.**
The route's `face` is an unbounded non-negative integer and the resolved list is *images*, not
faces. Measured, every card that gets a control has exactly two imaged faces, so a boolean would be
correct for every printing that exists — but the count is computable in one expression that mirrors
`resolve_face_images` exactly (`card_faces.filter((f) => f.image_uris).length`), and writing the
index makes the tile, the panel and the URL agree by construction. **Proposal:** store a face
index; advance `(index + 1) % imagedFaceCount`; render the control only when `imagedFaceCount > 1`.
Record that the modulo is a two-state toggle for 2,778 of 2,778 cards today — it is the rule's
spelling, not defensive generality.

**Q4. Where does flip state live? — proposal: a fifth store, `src/state/faces.ts`.**
UX-DR15: keyed by Scryfall printing uuid, per-tab, in memory, resets on refresh, **survives
`deck_changed`**, and applies everywhere the printing appears. A module-scope zustand store
satisfies all of it; a React state in `CardTile` satisfies none of it. **Proposal:**
`Record<string, number>` (id → face index, absent meaning 0), verbs `flipCard(cardId,
imagedFaceCount)` and `resetFaces()`, selector `useFaceIndex(cardId): number`, registered in
`STORES` with its `why`. **It is NOT cleared on a deck replacement** — c4-5's `deckMemory` clears
*inspection* because a pin from deck A can outrank deck B's cold-open target; a face index is keyed
by printing and is inert for a card that is not on the glass. Say so, because the two rules sit
three lines apart and the next reader will ask.

**Q5. One component or two? — proposal: one `FlipControl` container, mounted twice.**
UX-DR15 requires the panel to carry *"its own copy of the control at the same spec"*. Two
components is two chances to drift on a spec with a dozen rules. **Proposal:** a single
`src/containers/FlipControl/` taking `cardId` (and whatever Q3 needs), reading the cache and the
face store itself and **returning `null` when the card is not flippable** — so the "does this card
get a control?" question is asked once, in one place, by both mounts. Its stylesheet is
**not** card-shaped (pill radius), following the `QuantityBadge.css` precedent.

**Q6. The glyph — proposal: an inline `<svg aria-hidden="true">`, and the first one in `ui/src`.**
DESIGN.md asks for *"a stroke-based two-arrow rotate glyph … never anything that could read as a
mana or set symbol"* and specifies nothing else — no viewBox, no stroke width, no size. The design
system's only iconography note proposes a CDN icon set, which `DESIGN.md:418` bans by name and
NFR-06 rules out. The superseded working mocks used the text character `⇄` (U+21C4) with
`aria-label="Flip card"`; Voltglass moved the control to the top-left and asks for a **stroke**
glyph, so those are precedent for the label, not for the mark. **Proposal:** inline SVG,
`stroke="currentColor"`, `fill="none"`, sized ~16px inside the 28px disc, `aria-hidden="true"` with
the accessible name on the `<button>` from a `copy.ts`. Decide and record: viewBox, stroke width,
and that the two shipped "no SVG in this subtree" assertions (`StatePanel.test.tsx:61`,
`CardPlaceholder.test.tsx:81`) are in **other** components and stay green. Also decide whether a
guard should pin "no `<svg>` in `src/components/`" so the primitives tree does not acquire one by
drift.

**Q7. Does the art hook re-arm on a face change? — proposal: yes, `useCardArt(cardId, face)`.**
`useCardArt` keys on `cardId` alone, so a flip changes the `src` without re-arming the state
machine — and `?face=1` is always a cold browser-cache key on first flip. Two failure modes follow:
a flipped tile sits on the stale face with no well, and a tile whose **front** art failed renders
`CardPlaceholder` instead of an `<img>`, so there is nothing for a flip to change. **Proposal:**
give the hook a second key component so a face change re-arms to `loading` and both cached arms
(`complete && naturalWidth > 0` / `=== 0`) settle at the new key. It is shared by the tile and the
panel, so this is one edit for both.

**Q8. What happens to a flippable card whose art has FAILED? — needs a ruling.**
The control's existence is a fact about the *data* (`card_faces`); the placeholder is a fact about
the *art*. Options: render the control anyway (a flip may reach a face that loads), or suppress it
(a control over a placeholder has nothing to flip). Note that `?face=1` failing is a **different**
negative-cache key from `?face=0` failing, so the two faces genuinely fail independently. Whichever
is ruled, the `failed` branch in `CardTile` currently replaces the `<img>` entirely, so this is a
render-structure decision, not a styling one.

**Q9. Which array does the index address — `card_faces`, or the imaged subset? — proposal:
`card_faces`, valid because the control only renders when the two coincide.**
`resolve_face_images` returns only the **imaged** faces, in face order, so the two arrays differ for
a partially imaged card. Measured: **0 such rows exist**, and the backend's own return type cannot
represent a hole (`deferred-work.md:2765-2770`, ledgered as unowned/latent). **Proposal:** index
`card_faces` directly for text and pass the same index as `face` for the image, and state the
premise — this is only sound because the control renders only where **every** face is imaged.
Whoever meets the first partially imaged printing owns the entry the ledger already opened.

**Q10. The 3D rotation — proposal: two stacked faces with `backface-visibility: hidden`.**
DESIGN.md gives *"3D Y-rotation over `{components.dfc-flip.flip}`"* — 240ms, `ease-glide` — and
nothing else: no degrees, no perspective, no midpoint rule. Options: **(a)** both faces rendered as
stacked `<img>`s in a `preserve-3d` box, the back pre-rotated 180°, each `backface-visibility:
hidden`, and the box rotated on flip — pure CSS, correct, and the back face is fetched at mount so
the flip is warm and instant; **(b)** one `<img>` whose `src` swaps at the rotation's midpoint —
one fetch, but JS timing and a visibly wrong face during the first half unless the swap is exact.
**Proposal: (a)**, and price it in the open: it fetches the back face for every flippable tile at
mount — **6 extra images on the 99-card Atraxa deck, 10 on `Prismatic Dragon`** — which also
removes Q7's cold-flip problem entirely and changes `App.test.tsx`'s image-count arithmetic from
`tiles.length + 1` to a stated formula. Whatever ships, `transform` is registered `none !important`
on the **matching selector text** in `tokens.css`'s reduced-motion block and the enumerated
shipped-motion pin moves in the same commit.

**Q11. The control's state feedback — proposal: `aria-pressed`, and no announcement.**
UX-DR45 enumerates the live regions (connection pill, agent-view heading, the separate polite pin
region) and a flip is not among them; c4-5's H4/C1 finding is that transient changes must not flood
the queue. But a keyboard user needs to know which face is showing. **Proposal:** the control is a
toggle button carrying `aria-pressed={faceIndex !== 0}`, which gives state with no live region and
no new copy. Decide whether the accessible **name** is static ("Flip card") or names the target
face — a dynamic name is a data string, not copy, and would collide with rule 16.

**Q12. Alt text on a flipped face — proposal: inherit c4-4/c4-5's ruling and declare the
divergence again.**
UX-DR48 asks for alt *"face-specific for DFCs"*, but both shipped card surfaces already ship
`alt=""` on measured grounds (the tile's caption and the panel's `<h2>`-adjacent heading each name
the card exactly once). **Proposal:** keep `alt=""` on both. State the residual honestly: the
tile's **caption keeps showing the printing's combined name** (`Clearwater Pathway // Murkwater
Pathway`) while the tile shows the back face's art, and the panel's heading follows the face. That
is the same divergence c4-5 ledgered for the MDFC pin announcement, one surface further, and it
belongs on the epic manual-testing checklist rather than in a jsdom assertion.

**Q13. The focus ring on a control that sits over art — needs a ruling.**
The tile uses `--shadow-focus-ring-over-art` because its ring sits over arbitrary imagery
(gate finding **M5/C4**). The flip control also sits over art — but on top of a scrim-plus-blur
disc with a `--border-strong` edge, which is a *known* surface. No artefact rules on it. Options:
the standard `{components.focus-ring}` (2px `accent-bright`, 2px offset), or the over-art
treatment. Whichever is ruled, contrast is a **measurement**, not an assertion: `accent-bright`
`#B3BAFF` against `--scrim` `rgb(8 9 18 / 75%)` composited over unknown art.

**Q14. Does anything need to change in `CardGrid`? — proposal: no.**
Q2's wrapper lands inside `CardTile`, so `CardGrid` keeps its `{ boards }` prop and its single
flattening. Recorded so the answer is deliberate rather than an omission — c4-5 answered the same
question about the same file and kept it read-only.

## Acceptance Criteria

### The control — presence, absence and appearance

1. A card whose `card_faces` carry per-face `image_uris` renders a flip control on its tile:
   **28px circular, 32px hit area, pinned top-left inside `--space-2`** (FR-19, UX-DR15). It never
   collides with the quantity badge, which owns the top-right, and a test proves both corners are
   occupied independently on a card that has both.
2. A card whose `card_faces` carry **no** per-face `image_uris` — split, adventure, Omen —
   renders **no** control (FR-04, UX-DR15, AD-11). The predicate is the truthiness of per-face
   `image_uris`, mirroring `resolve_face_images`; it is **not** `'image_uris' in face`, **not**
   `card_faces !== null`, and **not** any layout string, because there is no layout data at any
   layer. Fixtures cover all four measured shapes (A: 35,036 / B: 368 / C: 2,778 / D: 79).
3. The control shares the quantity badge's material byte-for-byte from `DESIGN.md`'s
   `components.dfc-flip`: `var(--scrim)` background, `blur(6px)` backdrop, `1px solid
   var(--border-strong)`, `var(--text-primary)` foreground, `var(--radius-pill)`, **0.65 opacity at
   rest rising to 1.0 when its tile is hovered or focused**, and `var(--accent-bright)` when the
   control itself is hovered. Every `px` literal carries a DESIGN.md citation within a sentence.
4. The glyph is a **stroke-based two-arrow rotate mark** that could not read as a mana, set or
   planeswalker symbol (UX-DR7). It is `aria-hidden`; the control's accessible name comes from a
   `copy.ts` beside the component, registered in `COPY_MODULES`.
5. The control's chrome lives in a stylesheet that is **not** in `CARD_SHAPED` and therefore may
   spend `--radius-pill` — the `QuantityBadge.css` precedent, not a new exception (UX-DR4, rule 4).

### Behaviour

6. Clicking the control **flips the face and stops propagation** — it never sets, pins or clears
   the inspection (UX-DR15). Proven against the slice's verbs, not merely against a spy.
7. Enter and Space on the focused control flip the card. It is a real `<button>` (UX-DR47), so this
   is the browser's behaviour rather than an `onKeyDown` — and a test proves no `onKeyDown` was
   added.
8. The control sits in the Tab order **immediately after its own tile**, never as a trailing group
   (UX-DR15, UX-DR40). Asserted as document order over a rendered grid of ≥2 tiles where at least
   one is flippable, not as a `tabindex` value.
9. Flip state is keyed by **Scryfall printing uuid**, held at module scope, per-tab and in memory,
   and resets on a page refresh (UX-DR15). It survives a `deck_changed` re-render — a snap-back to
   the front face reads as a bug — and the test proves it by re-rendering over new boards rather
   than by asserting the store in isolation.
10. The same printing shows the same face **everywhere it appears** — grid tile and detail panel
    today; the contract is written for Epic 6's thumbnails (UX-DR15).
11. Hovering or focusing a flipped tile targets **that face**: the panel renders the back face's
    art, name, type line and oracle text (UX-DR15, UX-DR20). The panel's own art URL carries the
    same `face`, and `fromCard`'s per-field `??` fallback is preserved — ten flippable cards have a
    face with a null `type_line` and must not lose the top-level value.
12. The detail panel carries **its own copy of the control at the same spec**, pinned to the art
    box's top-left — the same component, mounted twice, not a second implementation (UX-DR15).
13. The face index is bounded by the **imaged**-face count, computed exactly as
    `resolve_face_images` computes it; `face=0` is never spelled in a URL, so the grid's front-face
    request stays byte-identical to c4-4's and the warm browser cache is not split.

### Motion, focus and the accessibility floor

14. Under `prefers-reduced-motion: reduce` the face **swaps instantly with no 3D rotation**
    (UX-DR42). Any shipped `transform` — or `scale` / `rotate` / `translate` individually — is
    registered `none !important` on the **matching selector text** in `tokens.css`'s reduced-motion
    block, `tokens.css:274`'s reserved row is honoured, and the enumerated shipped-motion pin in
    `token-usage.test.ts` moves in the same commit.
15. Nothing pulses, loops or alternates at any setting.
16. The control uses `:focus-visible`, never `:focus`; no `outline: none` in any spelling; its
    focus indicator is ruled explicitly (Q13) rather than inherited by accident, and any raised
    `z-index` stays below the overlay layer's `20`.
17. Its hit box is **≥ 24×24px measured**, not asserted from a stylesheet (UX-DR47) — the arithmetic
    is stated in the record and confirmed by the eye-check.
18. The control's presence does not change the tile's accessible name, which stays exactly one
    utterance (`Black Lotus ×4`, the pinned spelling). Whichever DOM shape Q2 rules, the name is
    re-proven, not assumed.
19. The DOM shape is **valid HTML**: no interactive element is a descendant of the tile's
    `<button>`, or if one is, the decision is recorded against a measured React 19 behaviour and a
    stated accessibility consequence (Q2, inherited deferral 4).

### The store, the category and the wiring

20. Flip state lives in a new slice under `src/state/`, registered in `store-writes.test.ts`'s
    `STORES` with `store` / `owner` / `why`, moving it **4 → 5**. **No component calls
    `setState`.** The module header states how it differs from the inspection slice's
    deck-transition clear and why it is not cleared there.
21. The control lands in `src/containers/`, not `src/components/` — it holds state and attaches
    handlers, which the primitives category bans (rule 1). Every new container module joins
    `CONTAINERS` in `shell.test.ts` in the **same commit** with an **exhaustive** import list, and
    the non-vacuity pin at `:1614` moves from `7`.
22. Any `src/api/` import from a new container is `import type`, not the inline-`type` form
    (c4-5's decision 2).
23. Whatever Q1 rules, the **cost is stated as a number**: how many extra requests a cold open
    makes for a 99-card deck, measured, and what that does to the `/api/cards/` call count
    `App.test.tsx` currently pins at 1.
24. `cardImageUrl` gains `face` as a parameter on the **one** existing function; no second template
    string exists anywhere in `src/`, and no Scryfall host appears in `src/`.

### The record, the gates and the ledger

25. **Each of the six inherited deferrals gets a written disposition** — done, declined with a
    reason, or re-homed by name (C2 retro R2). Deferral 1's *conclusion* is corrected on the record
    with the three cards named; deferral 3 is triggered and closed or explicitly carried.
26. Every claim the jsdom suite **cannot** carry is declared, not implied: the 3D rotation and the
    reduced-motion media query (jsdom evaluates neither), hover and rest **opacity**, the hit box in
    px, the flip as a screen reader announces it, and the warm/cold `?face=` image race.
27. Evasion probes are run against every new guard, and **a probe that passes is recorded**, not
    quietly fixed. At minimum: spell `face=0` into the grid URL; use `'image_uris' in face` instead
    of truthiness; render the control for a shape-B card; let the flip call an inspection verb; drop
    the reduced-motion registration; put the pill radius in a `CARD_SHAPED` file. Guards are proven
    through the **full `npm test`**, never a standalone file run — the standalone
    `token-usage.test.ts` runner crash is ledgered and confirmed live.
28. An eye-check is **performed, not assumed**, in a real browser against the running backend:
    `Prismatic Dragon` (1 flippable tile beside 9 faced-but-not-flippable ones) for AC 1 + AC 2 on
    one screen; `Atraxa Counter Cabinet v2 (owned)` for the six MDFC Pathways and the panel's
    face-swap; a `Sephiroth` deck for a back face with real rules text. Measure, do not describe:
    the hit box, the rest and hover opacities, the rotation, and the reduced-motion fallback with
    the OS setting actually on.
29. Ten gates green: `npm run lint`, `npm run format:check`, `npx tsc -b --force`, `npm test`,
    `npm run build`; `uv run pytest`, `ruff check .`, `ruff format --check .`, `mypy src/`,
    `mypy src/ --platform win32`. **`tsc -b --force`, not `tsc -b`** — the cache hides `TS2835`
    cascades.
30. The bundle is rebuilt and the `plugin/` mirror regenerated, both measured against c4-5's
    baseline (`index-D9iRSKVH.js` **213,797 B**, `index-tvpYICK1.css` **13,452 B**) and reported as
    changed or byte-identical **with the numbers**. This story mounts a new component in two places
    and ships new CSS, so **both** assets must change — a byte-identical JS bundle here means the
    control did not ship.
31. Python is untouched: `uv run pytest` stays at **2,501 passed / 1 skipped**.
32. Every measured number reproduced from this story's Dev Notes is **re-verified read-only** in
    Task 0 before it is relied on, and any that has moved is stated rather than smoothed over.

## Tasks / Subtasks

- [x] **Task 0 — Answer the fourteen open questions** (AC 1–32 depend on them). Cut the story branch
      `feat/companion-c4-6-dfc-flip-control` from `bd72fc0` on `feat/companion-c4`. Record each
      answer in this file **before** writing code. Do not start with an unanswered Q1, Q2, Q3, Q7 or
      Q10.
  - [x] Re-verify the corpus and deck measurements read-only (AC 32), including the four shapes,
        the 2,778/368/79 split, the "every flip-control card has exactly two imaged faces" claim,
        and the 42 flippable rows across 20 of 40 decks.
  - [x] **Measure React 19's actual behaviour for `<button>` inside `<button>`** — warning or
        silence, development or always — because Q2 turns on it.
- [x] **Task 1 — The face store** (AC 9, 10, 13, 20)
  - [x] `src/state/faces.ts`: the store, `flipCard`, `resetFaces`, `useFaceIndex`, and the module
        header stating why it is **not** cleared on a deck transition when inspection is.
  - [x] Register it in `store-writes.test.ts`'s `STORES` (4 → 5).
  - [x] `src/state/faces.test.ts`, including the modulo boundary and the absent-key default.
- [x] **Task 2 — The URL and the art hook** (AC 13, 24, and Q7)
  - [x] `imageUrl.ts` gains `face`, with `face=0` unspelled and the existing no-query assertion
        still passing untouched.
  - [x] `useCardArt` becomes face-aware; both cached arms settle at the new key; the tile and the
        panel share the one edit.
- [x] **Task 3 — The control** (AC 1–5, 6, 7, 16, 17)
  - [x] `src/containers/FlipControl/` — component, chrome stylesheet (not `CARD_SHAPED`), `copy.ts`,
        colocated test. It returns `null` when the card is not flippable, so the predicate has one
        home.
  - [x] The flippable predicate, mirroring `resolve_face_images` exactly, with fixtures for all four
        shapes.
  - [x] The glyph (Q6) and the focus-ring ruling (Q13).
  - [x] Join `CONTAINERS` with an exhaustive import list; move the pin from `7`. Join
        `COPY_MODULES` (7 → 8).
- [x] **Task 4 — Mount it on the tile** (AC 1, 6, 8, 18, 19, and Q2)
  - [x] The DOM shape Q2 ruled, with `CardTile.test.tsx:430`'s opt-out contract **re-proven** under
        it rather than re-worded.
  - [x] The pointer-handler placement, and a test that hovering the control does not clear the
        tile's inspection target.
  - [x] Tab order asserted as document order over a rendered grid.
- [x] **Task 5 — Mount it on the panel, and follow the face** (AC 11, 12)
  - [x] `fromCard` indexes the chosen face; the per-field `??` fallback survives (the ten null
        `type_line` faces).
  - [x] The panel's art URL carries the same `face`; the second mount sits at the art box's
        top-left.
  - [x] A test that a flip on the tile changes what the panel renders, in all four fields.
- [x] **Task 6 — Hydration** (AC 23, and Q1)
  - [x] Whatever Q1 ruled, with the request count measured and recorded, and `App.test.tsx`'s
        `/api/cards/` pin updated with the reason.
  - [x] If the sweep lands, close inherited deferral 2 (the `'Card // Card'` grouping) or state why
        it still does not close.
- [x] **Task 7 — The motion and its fallback** (AC 14, 15)
  - [x] The 3D Y-rotation per Q10 at `var(--motion-glide) var(--ease-glide)`.
  - [x] The reduced-motion registration on the **matching selector text**, `none !important`, and
        the enumerated shipped-motion pin moved in the same commit.
- [x] **Task 8 — Prove it, and declare what cannot be proven** (AC 25–32)
  - [x] Evasion probes against every new guard; record any that pass.
  - [x] The eye-check across the three named decks, with measurements rather than descriptions,
        including the reduced-motion setting actually enabled.
  - [x] Dispositions for all six inherited deferrals; declare the unprovable claims; add the epic
        manual-testing checklist entries (the caption/face-name divergence, the flip as a screen
        reader announces it).
  - [x] Ten gates; rebuild bundle + mirror; report the byte counts against the baseline.
- [x] **Task 9 — Set status `review` and STOP.** Do not raise the PR — Brad runs the three-layer
      review and raises it.

### Review Findings

Three-layer review 2026-08-06 (Blind Hunter / Edge Case Hunter / Acceptance Auditor). 21 raw
findings → 2 decisions, 10 patches, 3 defers, 5 dismissed (sub-frame focusout/focusin gap — no
paint intervenes; `:has()` is baseline in every engine this app meets; `cardImageUrl`'s
invalid-face collapse is the tested, specified behaviour; the frozen review patch omitting bundle
assets was the reviewer's own freeze excluding them — both mirrors verified byte-identical; a
one-off vitest worker flake that reproduced clean 1,255/1,255 on re-run).

- [x] [Review][Decision] **RULED (a), 2026-08-06: the documented posture stands.** The hydration
      sweep has no re-sweep after a mid-sweep backend blip while a deck is loaded — c4-2's
      recovery re-drive fires only from `refused`/`none`, never `deck` (`deck.ts:56-66`), so card
      reads that refuse during the sweep's ~1 s window stay unhydrated: no flip control, no
      hydrated panel text, until that card is individually inspected (which re-asks within the
      3-attempt budget — a blip burns only 1 of 3) or the page reloads. `cards.ts:100-108`
      documents reload as the recovery on purpose. Accepted as designed; the window is ledgered in
      `deferred-work.md` with the extend-the-edge option written down for whoever meets it live.
- [x] [Review][Decision] **RULED: ratified, 2026-08-06.** AC 8's Tab-order assertion runs over a
      hand-built `<ul>` scaffold (`CardTile.test.tsx:962-990`), not a rendered `CardGrid`. Ratified
      as the venue: the control mounts inside `CardTile`, so the real grid's document order follows
      structurally from the tile's own shape, and the CDP eye-check observed the Tab stop live
      mid-grid on the real 38-tile deck. The scaffold is the jsdom half; the eye-check is the
      grid-level half.
- [x] [Review][Patch] Focus half of Q2's pop repair is missing: Tabbing from a tile to its own
      control un-scales the frame and drops `--shadow-raise` — the exact defect the frame was
      built to prevent, on the keyboard path; reduced-motion users lose their only signal
      [ui/src/containers/CardTile/CardTile.css:85-86,156-163; tokens.css registration + pin move
      with the selector texts]
- [x] [Review][Patch] The preserve-3d scoping claim is false — `.card-faces` puts
      `transform-style: preserve-3d` and an armed transform transition on every tile; only the
      rotation is `[data-flipped]`-gated. Scope both to attribute presence so the load-bearing
      comments become true [ui/src/containers/FlipControl/FlipControl.css:199-212;
      ui/src/containers/CardTile/CardTile.tsx:398-403]
- [x] [Review][Patch] AC 9's rendered test is not "over new boards" — it re-renders one `CardTile`
      with a changed `quantity`, which local `useState` would also pass — and
      `faces.test.ts:116` attributes the missing test to `FlipControl.test.tsx`, where it does not
      exist [ui/src/containers/CardTile/CardTile.test.tsx:729]
- [x] [Review][Patch] Q6's ruling records the glyph "sized 16px"; the shipped arithmetic and the
      eye-check both say 18px — correct the ruling text [this file:1039]
- [x] [Review][Patch] `flipCard`'s docstring claims `Number.isFinite`; the code is
      `Number.isInteger` (stricter, correct) — fix the docstring and the test comment repeating it
      [ui/src/state/faces.ts; ui/src/state/faces.test.ts]
- [x] [Review][Patch] AC 27's named minimum probe "render the control for a shape-B card" is not
      among the twelve recorded — run it and record the result [this file, probe record]
- [x] [Review][Patch] `FlipControl.css`'s header says the rotation is NOT in this file and lives
      in CardTile.css/CardDetailChrome.css; the rotation rules are at the bottom of the same file
      and in neither of those [ui/src/containers/FlipControl/FlipControl.css header]
- [x] [Review][Patch] `CardTile`'s header misattributes the re-render granularity to the hooks
      "returning a NUMBER" — the subscription compares the per-id entry object; the derived number
      never enters any comparison [ui/src/containers/CardTile/CardTile.tsx:228-230]
- [x] [Review][Patch] `useCardArt`'s key-collision comment reasons from a false premise ("a `#`
      would have been percent-encoded before it reached a URL" — the hook receives the raw store
      id; encoding happens later in `cardImageUrl`) [ui/src/containers/useCardArt.ts]
- [x] [Review][Patch] AC 1's declared residue has an unledgered keyboard consequence: during the
      cold-open sweep (~1 s on the largest deck) flip controls materialise mid-Tab-traverse — the
      UX-DR40 defect Q1 priced against the lazy option. Ledger it and add it to the epic manual
      checklist [ui/src/App.tsx sweep; deferred-work.md]
- [x] [Review][Defer] An in-flight sweep is not cancelled on deck replacement — up to ~198 reads
      compete with the new deck's images [ui/src/App.tsx:213-216] — deferred, deck switching is
      Epic 5's; ledgered there
- [x] [Review][Defer] While the front face is `failed` the whole `.card-faces` block unmounts,
      discarding the back face's in-flight load events; flipping out re-requests the known-failed
      front [ui/src/containers/CardTile/CardTile.tsx failed-art arm] — deferred, self-heals on
      remount; negative cache answers the re-request
- [x] [Review][Defer] Three hand-rolled copies of the flippable wire fixture (CardTile.test,
      FlipControl.test, CardDetail.test) will drift when `CardFace` gains a field — deferred,
      test-only refactor

## Dev Notes — References

- Story 4.6 and the UX-DR inventory:
  [epics-companion-app.md:2035-2082](../planning-artifacts/epics-companion-app.md); UX-DR15 `:409`,
  UX-DR4 `:351`, UX-DR7 `:364`, UX-DR14 `:402`, UX-DR16 `:422`, UX-DR20 `:442`, UX-DR22 `:453`,
  UX-DR39 `:558`, UX-DR40 `:566`, UX-DR41 `:574`, UX-DR42 `:577`, UX-DR44 `:590`, UX-DR45 `:597`,
  UX-DR46 `:603`, UX-DR47 `:608`, UX-DR48 `:611`; epic note `:794`; PRD amendment owed `:323`
- Visual contract:
  [DESIGN.md:386](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md)
  (the `dfc-flip` prose), `:160-170` (the frontmatter group), `:120-127` (motion), `:299-318` (the
  contrast table), `:358` (the glass material), `:372` (the mock does **not** demonstrate this
  control), `:283`/`:417`/`:418` (the brand and delivery bans)
- Behavioural contract:
  [EXPERIENCE.md:84](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md)
  (the component row), `:23` (the governing principle — flipping is one of only two permitted
  clicks), `:141` (Tab order), `:146` (focus-visible), `:152` (reduced motion), `:155` (hit
  targets), `:157` (alt text)
- UX gate:
  [validation-report-2026-07-25.md:43](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/validation-report-2026-07-25.md)
  (H2 — this control had no spec in either spine), `:123` (H2 was miscategorised; FR-19 always
  mandated it), `:130` (the disposition, which is the closest thing to a design-decision record),
  `:57,87` (M4/C3), `:59,88` (M5/C4 — the focus ring over art)
- Architecture:
  [ARCHITECTURE-SPINE.md:242-270](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md)
  (AD-11 — face handling keys on per-face `image_uris`, never a layout string), `:272-290` (AD-12)
- Backend, already complete: `src/companion/app/images.py:463` (`resolve_face_images` and the four
  measured shapes), `src/companion/app/routes/cards.py:223` (the route, the `face` parameter and its
  docstring), `src/data/schemas/card.py:35` (`IMAGE_DISCRIMINATOR`, stated once and gated as a
  family), `:65` (`CardFace`), `tests/unit/companion/test_images.py:89` (twelve resolver tests),
  `tests/unit/companion/test_routes_card_image.py:130` (the wire-level face tests, keyed on bytes)
- Conventions: `ui/README.md:545-569` (containers), `:779-834` (the card shape), `:858-893` (motion
  and the focus ring), `:869-877` (the reduced-motion gate and its `!important` requirement),
  `:1200-1244` (the store, the one door, no panel on a card refusal)
- Ledger: `deferred-work.md:2027-2034` (`card_faces` untyped — **home: c4-6**), `:2765-2770` (the
  partially imaged card, unowned/latent), `:2989-2997` (the `images.py` split, C4 retro),
  `:3515-3520` (the `'Card // Card'` grouping — **home: c4-6**), `:3743-3748` (`<div>`-in-`<button>`),
  `:3750` (the selector-text motion guard — **triggered here**), `:3778-3786` (the oracle scroller,
  c4-11)
- Previous story:
  [c4-5-persistent-card-detail-panel-with-transient-and-pinned-inspection.md](c4-5-persistent-card-detail-panel-with-transient-and-pinned-inspection.md)
  — Q1 (what hydration actually buys), Q8 (the slice's location-agnostic verbs), Q13 (`alt=""`), and
  the PR #44 P1 that made hover and focus two slots

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow.

### Debug Log References

#### Task 0 — the measurements, re-verified read-only at `bd72fc0` (AC 32)

Run against `src.paths.data_dir()/cards.db` in `mode=ro`. **Every headline number in Dev Notes
reproduces exactly**; two are corrected and one is sharpened.

| Claim | Story | Measured | |
|---|---:|---:|---|
| cards / decks / deck_cards rows | 38,261 / 40 / 2,027 | 38,261 / 40 / 2,027 | ✅ |
| Shape A — top-level `image_uris`, no faces | 35,036 | 35,036 | ✅ |
| Shape B — top image + unimaged faces | 368 | 368 | ✅ |
| Shape C — no top image, every face imaged | 2,778 | 2,778 | ✅ |
| Shape D — faces, images nowhere | 79 | 79 | ✅ |
| rows carrying BOTH | 0 | 0 | ✅ |
| partially imaged rows | 0 | 0 | ✅ |
| imaged-face count on every shape-C card | exactly 2 | `{2: 2778}` | ✅ |
| faced cards (any `card_faces`) | 3,225 | 3,225 | ✅ |
| reversible-art printings among the 2,778 | 2,166 | 2,166 (→ 612 true DFCs) | ✅ |
| face-count histogram, all faced cards | 2→3,222 · 3→2 · 5→1 | identical | ✅ |
| the three 3-/5-face cards get no control | yes | **0 imaged faces each**, named below | ✅ |
| flippable cards with a null `type_line` face | 10 | 10 | ✅ |
| longest back-face `oracle_text` | 1,232 | 1,232 (`Magic and Minions // …`) | ✅ |
| flippable deck rows / decks holding one | 42 / 20 of 40 | 42 / 20 of 40 | ✅ |
| reversible printings in any live deck | 0 | 0 | ✅ |
| `' // '` predicate over faced cards | 3,194, misses 31 | 3,194, misses 31 | ✅ |
| `' // '` predicate over deck rows | 65 | 65 | ✅ |

The three cards `deferred-work.md:2032` warns about, named and measured: `Smelt // Herd // Saw`
(3 faces, **0 imaged**), `There // They're // Their` (3, **0**), `Who // What // When // Where //
Why` (5, **0**). All three are shape B. **The ledger's conclusion is corrected on the record: a
`[front, back]` reading is wrong for zero cards that get a flip control.**

**Correction 1 — the join is 1,999 rows, not 2,027.** `deck_cards` holds 2,027 rows but 28 are
orphaned by DECK id (the c4-2 record measured the same 28). So "42 of 2,027" is really **42 of the
1,999 rows that join to a real deck**; the flippable count itself is unchanged.

**Correction 2 — `Prismatic Dragon` gets ONE extra image under Q10, not ten.** Dev Notes' Q10
prices the back-face prefetch at *"6 extra images on the 99-card Atraxa deck, 10 on `Prismatic
Dragon`"*. Measured: that deck has **1 flippable row** (`Marang River Regent // Coil and Catch`)
beside **9 faced-but-not-flippable** ones (the Tarkir Omen dragons). The 10 is the faced count, not
the flippable one. Atraxa's 6 is right.

**Sharpened — the sweep's real bound.** `max(count(distinct card_id)) over decks` = **99**, on both
Atraxa decks. So Q1's sweep is bounded at 99 requests for the largest real deck and fewer for all
39 others.

Deck-level detail, reproduced for the eye-check:

- `Prismatic Dragon` (38 rows): **1 with** a control, **9 without** — AC 1 and AC 2 on one screen.
- `Atraxa Counter Cabinet v2 (owned)` (99 rows): **6 with**, all MDFC Pathways, **0 faced-but-not**.
- `Ayara Black Devotion` (69 rows): **3 with** (`Tergrid`, `Graveyard Trespasser`,
  `Agadeem's Awakening`), **3 without** (`Emeritus of Woe`, `Foulmire Knight`, `Murderous Rider`).

#### Task 0 — React 19.2 `<button>` inside `<button>`, MEASURED (the fact Q2 turns on)

A throwaway probe rendered the nested shape under the real `dom` project and captured
`console.error`:

```
console.error calls = 1
  "In HTML, %s cannot be a descendant of <%s>.\nThis will cause a hydration error.%s"
innerHTML  = <button …data-outer><span>caption</span><button …data-inner>flip</button></button>
outer.contains(inner) = true
buttons found by role = 2
```

Three facts, and they do not all point the same way:

1. **React 19.2 does warn**, in the exact wording the story predicted. Not silence.
2. **The warning is development-only.** `grep -c "cannot be a descendant of"` →
   `react-dom-client.development.js` **1**, `react-dom-client.production.js` **0**. So the console
   noise never reaches a shipped bundle — but it fires on every `npm run dev` render and every
   jsdom render of a flippable tile, which is real friction rather than a shipped defect.
3. **The invalid nesting survives into the DOM.** React builds imperatively, so unlike a parsed
   HTML document there is no parser to unnest it: the tree really does contain a `<button>` inside
   a `<button>`, and what a screen reader does with that is undefined rather than merely untidy.

Fact 3 is what decides Q2 — see the ruling.

A second probe confirmed the property the sibling shape depends on: `mouseenter`/`mouseleave` on a
wrapper are not re-fired by movement between the wrapper's own descendants (they do not fire on
descendant transitions at all), so a wrapper that contains both the button and the control is
exactly as immune to "the pointer moved onto the control" as the button was to "the pointer moved
onto the badge".

#### Task 0 — the fourteen rulings

**Q1. How does a tile learn it has a back face? — RULED (a), as proposed: hydrate the deck's
distinct card ids once, after the grid has committed.**
(b) is an MCP-visible schema change priced in Dev Notes; (c) fails the epic's own literal AC text
(*"**When** its tile renders **Then** a 28px circular flip control appears"*,
`epics-companion-app.md:2043`) and would materialise a Tab stop mid-traverse. The `' // '` name
filter is **rejected** for the reason the story recorded and one more it did not: as a *sweep*
filter it misses 31 corpus cards, and as a *control* predicate it would be wrong in the opposite
direction too — it selects shape B (`Murderous Rider // Swift End`), which AC 2 forbids and which
`Prismatic Dragon` exists to catch.
**Two deviations from the proposal's shape, both to protect NFR-05 and both stated:**
- **The sweep does not live in `deck.ts`.** It is `hydrateDeckCards(cardIds)` in `src/state/cards.ts`
  — beside `seedCardSummaries` and `hydrateCard`, in the module that owns the cache — so the cache
  owns its own sweep and `deck.ts` gains nothing.
- **It is fired from a `useEffect` in `App.tsx`, not from the boot.** This is an ordering decision
  with a mechanism rather than a preference: React runs effects **after** the DOM commit, and the
  commit is what sets every `<img src>`, so by the time the sweep issues its first request the
  browser has already queued all ~99 image requests. Calling it inside `createDeckBoot` (beside
  `seedCardSummaries`) would issue 99 JSON requests **before** React had rendered a single tile,
  putting the whole sweep in front of the pictures in a 6-connection-per-origin queue. No timer is
  involved — React's own effect ordering is the deferral. `App.tsx` is permitted to hold state and
  hooks (`posture.test.ts:342` says so in as many words); it may not reach the wire, and it still
  does not.
Cost, stated as AC 23 requires: **≤ 99 extra `GET /api/cards/{id}` requests per deck per tab**, once,
deduped and capped by `hydrateCard`; measured live in Task 8. `App.test.tsx`'s
`callsTo(fetchMock, '/api/cards/')` pin moves **1 → 2** (its fixture holds two distinct cards) and
`toHaveBeenCalledTimes` **4 → 5**.

**Q2. Inside the tile's `<button>` or beside it? — RULED: beside it, in a positioned wrapper.**
Decided by measured fact 3 above, not by the content model in the abstract: the invalid tree really
exists at runtime, and a `<button>` inside a `<button>` is not reliably exposed as a separate
control by assistive technology — which would break **AC 7** (Enter/Space on the focused control)
and **AC 8** (its Tab stop) on real hardware while passing every jsdom assertion. A gate that only
fails on hardware nobody in this project runs is the worst available outcome.
`CardTile` renders `<div className="card-tile-frame">` holding the `<button>` and the control as
**siblings**; the caption stays outside the frame, so the tile's structure is
`frame(button, control) + caption` and the frame's box coincides exactly with the card box (the
button is `display: block; width: 100%` with `card-shape`'s aspect ratio).
**All four pointer/focus handlers move to the frame; `onClick` stays on the button.** `onFocus`/
`onBlur` move too — they are `focusin`/`focusout` and bubble, so Tabbing from the tile to its own
control keeps the tile's inspection target instead of dropping it, which is PR #44's P1 defect one
element further out.
**The consequence the proposal did not price, found while ruling and repaired here:** with the
control as a sibling, `.card-tile:hover` is FALSE while the pointer is on the control — so the
hover pop and the raised shadow would drop out on exactly the gesture the control exists for.
The repair keeps **every specificity in `CardTile.css` byte-identical** so c4-4's whole cascade
argument survives verbatim: `.card-tile:hover` becomes
`:where(.card-tile-frame):hover .card-tile`, which is **(0,2,0)** — `:hover` counts, `:where()`
contributes zero — exactly what `.card-tile:hover` was. `.card-tile.is-live:hover` becomes
`:where(.card-tile-frame):hover .card-tile.is-live`, still **(0,3,0)**. Nothing else in the file
moves, and stylelint's `no-descending-specificity` sees the same ordering it saw before.
`CardTile.test.tsx:430`'s premise is now false ("descendant") and its **behaviour** is still true;
it is re-proven under the new shape rather than re-worded, and a new test proves the real control.

**Q3. Boolean toggle or face index? — RULED: an index, cycled modulo the imaged-face count**, as
proposed. Recorded: the modulo is a two-state toggle for **2,778 of 2,778** cards today.

**Q4. Where does flip state live? — RULED: a fifth store, `src/state/faces.ts`**, as proposed.
`Record<string, number>`, verbs `flipCard(cardId, imagedFaceCount)` / `resetFaces()`, selector
`useFaceIndex(cardId)`. **Not** cleared on deck replacement, and the module header says why beside
`deckMemory`'s opposite rule.

**Q5. One component or two? — RULED: one `FlipControl`, mounted twice**, returning `null` when the
card is not flippable, as proposed.

**Q6. The glyph — RULED: inline `<svg aria-hidden="true">`, and it is the first in `ui/src`.**
`viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `stroke-width="2"`,
`stroke-linecap="round"`, `stroke-linejoin="round"`, sized **18px** inside the 28px disc (28 − 2×1
border − 2×4 padding; this ruling first recorded "16px" while the shipped arithmetic and the
eye-check both said 18 — corrected at review 2026-08-06) — the values are recorded here because
DESIGN.md specifies none of them. Two arcs with two arrowheads, drawn
open so it cannot read as a closed mana pip or a set symbol (UX-DR7). The accessible name is on the
`<button>`, from `FlipControl/copy.ts`, registered in `COPY_MODULES` (7 → 8).
**Decided and recorded: NO new "no `<svg>` in `src/components/`" guard.** The two shipped
absence-assertions (`StatePanel.test.tsx:61`, `CardPlaceholder.test.tsx:81`) are in other
components and stay green; a tree-wide ban would fall hardest on the one category that could
legitimately own an icon later (a presentation-only `Icon` primitive), which is a rule written
against a future story rather than against a defect.

**Q7. Does the art hook re-arm on a face change? — RULED yes: `useCardArt(cardId, face)`**, as
proposed. Both cached arms settle at the new key; one edit serves the tile and the panel.

**Q8. A flippable card whose art has FAILED — RULED: the control still renders, and the art state
is the CURRENTLY SHOWN face's.**
The alternative (suppress it) permanently strands a card on a face whose picture failed, when the
other face may well load — and `?face=1` is a different negative-cache key, so the two genuinely
fail independently. So: `useCardArt` is called for each face, the shown face governs the well and
the named placeholder exactly as today, and the control sits over the placeholder when that is what
is drawn. A flip out of a failed face is therefore possible; a flip into one draws the placeholder.

**Q9. Which array does the index address? — RULED: `card_faces` directly**, as proposed, sound
because the control renders only where every face is imaged (0 partially-imaged rows, re-measured).

**Q10. The 3D rotation — RULED (a): two stacked faces with `backface-visibility: hidden`**, as
proposed, with one scoping decision: **the back `<img>` is rendered only for a flippable card**, so
a non-flippable tile's DOM is byte-identical to c4-4's and `App.test.tsx`'s `tiles.length + 1`
image arithmetic needs no change for its (non-flippable) fixture. Priced with the corrected number:
**6 extra images on the 99-card Atraxa deck, 1 on `Prismatic Dragon`, 42 across all 40 decks.**
(b) was declined on a mechanism rather than a preference: a midpoint `src` swap needs a JS timer,
and under `prefers-reduced-motion` `--motion-glide` is `0ms`, where `transitionend` is exactly the
event that stops being dependable.

**Q11. State feedback — RULED: `aria-pressed={faceIndex !== 0}` and a STATIC name**, as proposed.
No live region. The name stays `Flip card`: a name that named the target face would be a data
string in a read-aloud attribute, which is `copy-rules.test.ts`'s attribute half and rule 16.

**Q12. Alt text on a flipped face — RULED: `alt=""` on both surfaces**, inheriting c4-4/c4-5 and
declaring the divergence again. The residual, stated: the tile's caption keeps the printing's
combined name while the art shows the back face; the panel's heading follows the face. Epic
manual-testing checklist, not a jsdom assertion.

**Q13. The focus ring on a control that sits over art — RULED: the over-art composite**
(`--shadow-focus-ring-over-art`) plus the authored outline, the same treatment gate finding M5/C4
gave the tile. The arithmetic that decides it: the disc is **28px** and the indicator is **4px** of
ring around it, so the outer band lands on card art rather than on the known scrim — the disc is
only a "known surface" for the inner band. Contrast is therefore a composite question (`--focus-ring`
`#B3BAFF` on `--scrim` `rgb(8 9 18 / 75%)` over unknown art), and the composite's
`--surface-base` outer band is what makes it legible over a light painting and a dark one alike.
`z-index` stays below the overlay layer's 20.

**Q14. Does anything need to change in `CardGrid`? — RULED no**, as proposed. Q2's frame lands
inside `CardTile`; `CardGrid` keeps `{ boards }` and its single flattening, and is not edited.

### Completion Notes List

#### What shipped

The DFC flip control, mounted twice from one component, with the face held in a fifth store slice
keyed by Scryfall printing uuid. All fourteen open questions answered before any code was written;
**eleven as proposed, three with stated deviations** (Q1's sweep home and firing point, Q10's
scoping of the back `<img>`, Q13's ruling where the story asked for one).

- `src/state/faces.ts` — the fifth slice. `Record<string, number>`, `flipCard` / `resetFaces` /
  `useFaceIndex`, registered in `STORES` (4 → 5). Not cleared on a deck replacement, with the
  reason stated beside `deckMemory`'s opposite rule.
- `src/containers/imagedFaces.ts` — the ONE mirror of `resolve_face_images`, at the root of the
  containers tree because two components need the answer (`filled.ts`'s precedent).
- `src/containers/FlipControl/` — the control, its chrome (not `CARD_SHAPED`), its `copy.ts`
  (`COPY_MODULES` 7 → 8) and its suite. It also owns the shared `.card-faces` / `.card-face`
  3D machinery, because the flip belongs to neither surface.
- `CardTile` — a `.card-tile-frame` wrapper, the pointer/focus handlers moved onto it, two stacked
  faces, and a cascade repair that keeps every specificity in `CardTile.css` byte-identical.
- `CardDetail` — `fromCard` indexes the chosen face, the art URL carries it, the two art branches
  merged into one box so the control has one home, and the panel's own copy of the control.
- `App.tsx` — the deck-wide hydration sweep, in an effect, with its measured cost in the comment.
- `cardImageUrl` gained `face` on the ONE function; `useCardArt` gained a `(cardId, face)` key.

#### Three deviations from the proposals, each stated with its reason

1. **Q1's sweep does not live in `deck.ts`** — it is `hydrateDeckCards` in `src/state/cards.ts`
   (the cache owns its own sweep) and it is fired from a `useEffect` in `App.tsx` rather than from
   `createDeckBoot`, so it is off the render's critical path.
2. **Q10's back `<img>` renders only for a flippable card**, so a non-flippable tile still issues
   exactly one image request and 93 of Atraxa's 99 tiles are untouched.
3. **The panel's face swap uses the same 3D machinery as the tile.** DESIGN.md's *"its own copy of
   the control at the same spec"* is ambiguous about the animation; sharing the classes means one
   registration pair covers both surfaces, and `CardDetail.css`'s own *"NO MOTION, DELIBERATELY"*
   claim stays literally true because the classes are declared in `FlipControl.css`.

#### The two evasion probes that PASSED, recorded rather than quietly fixed (AC 27)

Twelve probes run, every one through the **full `npm test`** (never a standalone file run — the
ledgered `token-usage.test.ts` runner crash). Ten were caught. **Two passed, and both were real:**

- **Probe (c) — weaken the predicate from `imagedFaces < 2` to `< 1`.** The whole suite stayed
  green, because **no fixture had a card with exactly ONE imaged face**, so nothing distinguished
  "has pictures" from "has pictures to flip between". 0 such rows exist today, which is exactly
  why the gap was invisible — and it is the population `deferred-work.md:2765-2770` already has an
  open entry for. A control on such a card would render and then flip to a `404`. Closed with a
  named test; the probe now fails.
- **Probe (g) — revert `useCardArt`'s key to `cardId` alone, undoing Q7's whole repair.** The
  whole suite stayed green, and the cause is an interaction between two of this story's own
  rulings: Q10 gives each face its own `<img>` and therefore its own hook instance, so neither
  consumer ever hands ONE instance a changed face. The repair is still correct (it is what makes
  the hook right for a third imaged face, and for any later consumer that swaps faces in one
  element), but its subject was invisible. Closed by adding `src/containers/useCardArt.test.ts`,
  which changes the face directly; the probe now fails.

The other ten: spelling `face=0` into the grid URL; `'image_uris' in face` instead of truthiness;
the flip calling an inspection verb; dropping the flip's reduced-motion registration; a pill radius
in a `CARD_SHAPED` file; dropping `stopPropagation`; dropping the deck sweep; dropping the control
from the tile; smuggling face DATA into `aria-label`; and moving the pointer handlers back onto the
button. All ten red.

**A thirteenth probe, run at review (2026-08-06) because AC 27 names it and the record above did
not show it by name: "render the control for a shape-B card."** Injected by weakening
`useImagedFaceCount` to `faces.length` — counting faces rather than imaged faces, which is exactly
what puts a control on every split/adventure/Omen card. Caught RED by five named tests in
`FlipControl.test.tsx` (shape B, shape D, the truthiness-not-key-presence test, the
partially-imaged closure from probe (c), and the empty-map JS/Python divergence test), through the
full `npm test`: 5 failed / 1,250 passed. Reverted; the predicate stands.

#### The eye-check — PERFORMED, in headless Chrome over CDP, against the running backend (AC 28)

Every number below is `getComputedStyle` / `getBoundingClientRect` / Chrome's own accessibility
tree, not a description.

**`Prismatic Dragon` — AC 1 and AC 2 on one screen.** 38 tiles, **exactly 1 control**, on
`Marang River Regent // Coil and Catch`; the 9 Tarkir Omen dragons get none.

| Measured | Value | Spec |
|---|---|---|
| disc | **28 × 28 px** | `components.dfc-flip.size` |
| hit box (incl. `::after`) | **32 × 32 px** | `hit-area`; UX-DR47 floor is 24 |
| inset from the card's corner | **top 8, left 8** | `{spacing.2}` |
| quantity badge | right 8, top 8, **`overlaps: false`** | AC 1's two corners |
| rest opacity | **0.65** | `rest-opacity` |
| radius | **999px** | `{rounded.pill}` |
| background | `rgba(8, 9, 18, 0.75)` | `--scrim` |
| border | `1px solid rgb(61, 66, 102)` | `--border-strong` |
| backdrop | **`blur(6px)`** | `backdrop` |
| foreground | `rgb(233, 235, 245)` | `--text-primary` |
| glyph | **18 × 18**, `fill: none`, 4 paths | Q6's recorded values |
| z-index | **3** | above the tile's 2, below the overlay's 20 |
| flip transition | **`transform 0.24s`** | `--motion-glide` |
| back `<img>` transform | `matrix3d(-1,0,0,0, 0,1,0,0, 0,0,-1,0, 0,0,0,1)` | `rotateY(180deg)` |
| both faces | `naturalWidth: 488` | the flip is **warm**, not a cold fetch |

**Hover, with a real CDP pointer.** Pointer on the card: control opacity **1**, frame
`matrix(1.06,…)`, z-index 2. Pointer moved **onto the control**: frame still `matrix(1.06,…)`, tile
still `is-live`, control colour `rgb(179, 186, 255)` = `--accent-bright`. **That is Q2's repair
confirmed on a real screen** — the card does not un-pop when you reach for its own control.

**Focus ring (Q13).** `outline: rgb(179,186,255) solid 2px` at offset 0, plus
`box-shadow: rgb(179,186,255) 0 0 0 2px, rgb(18,20,31) 0 0 0 4px` — the over-art composite.

**Tab order (AC 8).** Read as document order over the rendered 38-tile grid: `…card-tile,
card-tile, card-tile is-live, **flip-control :: Flip card**, card-tile, card-tile…` — immediately
after its own tile, in the middle of the grid, never a trailing group.

**Accessible names, from Chrome's own AX tree (AC 18).** Tile →
`button | MARANG RIVER REGENT // COIL AND CATCH ×3`. Control → `button | Flip card | pressed: true`.
The control does not join the tile's name, and the name is still exactly one utterance.

**The panel (AC 11, AC 12).** Pinned the flippable tile, then clicked the **panel's own** control:
name `Marang River Regent` → `Coil and Catch`, type `Creature — Dragon` → `Instant — Omen`, pips
`{C}{U}{U}` → `{C}{U}`, `aria-pressed` false → true, `data-flipped` false → true, and **the tile
behind it followed** (AC 10). Panel control: 28 × 28 at inset 8/8 inside `.card-detail-art`. Its
URLs: `?size=large` and `?size=large&face=1`, both `naturalWidth: 672`.

> **A false bug avoided, worth recording.** The panel's oracle text did not change on that flip.
> Checked against the database rather than filed: `Marang River Regent // Coil and Catch` genuinely
> carries **identical `oracle_text` on both faces** — a Scryfall quirk for Omen printings. The
> render is correct. An eye-check that stopped at "the oracle didn't change" would have raised a
> defect that does not exist.

**`Atraxa Counter Cabinet v2 (owned)`.** 99 tiles, **6 controls**, all six MDFC Pathways named.
**106 image requests = 99 fronts + 6 backs + 1 panel `size=large`** — Q10's price confirmed exactly.

**A Sephiroth deck.** 20 tiles, 1 control. Flipping the panel: `Sephiroth, Fabled SOLDIER`
(`Legendary Creature — Human Avatar Soldier`, 264 chars) → `Sephiroth, One-Winged Angel`
(`Legendary Creature — Angel Nightmare Avatar`, 292 chars). All four fields, on real rules text.

**Reduced motion, with the setting ACTUALLY ON** (`--force-prefers-reduced-motion`;
`matchMedia(...).matches === true` confirmed in-page). Hover pop `transform: none`. Faces
`transform: none`. Unflipped: front `visible`, back **`hidden`**. Flipped: front **`hidden`**, back
`visible`. **The face swaps instantly with no rotation** — and this is the measurement that
vindicates the two `visibility` rules: without them both faces would face the viewer and the back
would cover the front at every setting.

#### Q1's cost, measured properly (AC 23) — and a claim of mine that was WRONG

`App.test.tsx`'s `/api/cards/` pin moved **1 → 2** (two distinct cards in its fixture) and the
total call count **4 → 5**. On the real 99-card Atraxa deck the sweep issues **99** card reads —
one per distinct id, ceiling confirmed live.

**The comment I first wrote in `App.tsx` claimed the effect places the sweep *behind* the images.
Measured, that is false and it has been corrected in the file.** Across four cold-cache runs the
first card read starts **6–10 ms BEFORE** the first image (108/114, 757/765, 583/593, 105/113 ms):
the commit sets the `src` attributes but the browser dispatches those loads asynchronously, and the
effect gets there first. React's ordering buys *"not on the render path"*, not *"behind the
pictures"*.

The wall-clock price, same deck, same machine, fresh browser profile each run, time from navigation
to the **last** of the deck's images:

| | run 1 | run 2 | run 3 | run 4 |
|---|---:|---:|---:|---:|
| with the sweep | 1,594 | 1,793 | 1,795 | 847 ms |
| without it | 343 | 753 | 538 | 352 ms |

So the **tail** of a cold open roughly triples — about **+1.2 s** on the largest real deck — while
first paint is untouched (32–128 ms either way, because the grid draws from the summary tier and
never waits). It is a cold-open cost, once per deck per tab, and it is the price of AC 1 being true
at all. **Flagged for review as the sharpest trade this story makes.**

#### The six inherited deferrals — a written disposition each (AC 25)

1. **`card_faces` crosses the wire untyped (`:2027-2034`) — CLOSED, and its conclusion CORRECTED.**
   The typing half was already closed (c3-5's Pydantic model, c4-5's TS alias). The entry's
   conclusion — *"a `[front, back]` destructuring is wrong for three real cards"* — is **wrong for
   this story's purposes and the correction is on the record**: all three cards are named
   (`Smelt // Herd // Saw`, `There // They're // Their`,
   `Who // What // When // Where // Why`), all three have **0 imaged faces**, and all three get no
   control. Re-measured at Task 0. A `[front, back]` reading is wrong for **zero** cards that get
   a flip control.
2. **The `'Card // Card'` grouping cannot be done from the deck payload (`:3515-3520`) — the
   blocker is REMOVED; the fix is RE-HOMED to c4-7.** The entry's own condition was *"if [a
   hydration sweep] lands, the grouping can read the front face properly for the ids already
   hydrated"*. It landed: every deck card is hydrated after boot, so `card_faces[0].type_line` is
   now available for the 2,274 corpus rows with a degenerate type line. This story does not spend
   it, because **`deckGroups.ts` is the grouper and c4-7 owns the deck list** — grouping here would
   be the second derivation AD-12 exists to prevent. Re-homed to **c4-7** by name, with the
   99-fetch objection now void. Still 0 such rows in any live deck.
3. **The reduced-motion transform guard compares selector text (`:3750`) — TRIGGERED and CLOSED,
   twice.** Once by the flip's two rotations, and once more than the entry anticipated: the hover
   pop's own selector moved from `.card-tile:hover` onto `.card-tile-frame:hover`, so c4-4's
   registration had to move with it. Both are false-failure directions, both repaired by writing
   the matching selector, and the enumerated shipped-motion pin moved in the same commit (2 → 4).
4. **`CardPlaceholder` renders a `<div>` and `<button>` takes phrasing content only
   (`:3743-3748`) — RE-DECIDED here, and the harder version of it is now CLOSED.** Q2 is the same
   seam one level worse — an *interactive* descendant rather than a flow one — and it is ruled
   against: the flip control is a sibling, and `CardTile.test.tsx` asserts
   `tile.querySelectorAll('button, a, input, select, textarea')` is empty. **The original entry is
   NOT closed**: c4-3's placeholder `<div>` is still inside the tile's `<button>` on the failed-art
   path. It stays open, unchanged, and is re-homed to **c4-11** (the keyboard/semantics story) with
   this story's measurement attached — React 19.2 warns in development only, and the tree really
   does keep the invalid nesting.
5. **The `images.py` split (`:2989-2997`) — Home: the C4 retrospective, and this story feeds it
   evidence.** As the first caller of `face=`, the finding is: **the pacer, the disk cache and the
   negative cache all need nothing at a non-zero face key.** `?face=1` behaves as an ordinary
   distinct key throughout — both back faces reached `naturalWidth: 672`/`488` on first request in
   the eye-check, and the 6 extra Atraxa images cost 6 ordinary fetches. No new pressure on that
   module; the split decision stands unchanged for the retro.
6. **The 21em oracle scroller is keyboard-unreachable (`:3778-3786`) — Home: c4-11, NOT fixed
   here, and this story could not make it fire either.** The clamp measured **294px** live and the
   deepest real back face in the eye-check was **126px** (`Sephiroth, One-Winged Angel`, 292
   chars). The 1,232-character back face that would fire it
   (`Magic and Minions // Magic and Minions (cont'd)`) is in **no live deck**, so the claim that
   this story is *"the first that can make the clamp fire in a real deck"* is **measured false**.
   Stated rather than smoothed over. The entry stays with c4-11, unchanged.

Three more were touched and are noted: the **standalone `token-usage.test.ts` runner crash** (every
probe was run through the full `npm test`), the **jsdom accessible-name spelling limit** (closed for
this story by reading Chrome's own AX tree instead), and c4-5's **`aria-query` maps `<header>` to
`banner`** blind spot (untouched — no new titled `Panel` ships here).

#### What the suite CANNOT carry, declared rather than implied (AC 26)

Every one of these is covered by the eye-check above, and each is named in the file that cannot
prove it:

- **The 3D rotation and the reduced-motion media query.** jsdom evaluates neither, and
  `getComputedStyle(el).transform` returns `''` — it would pass for the wrong reason.
- **Every opacity**: 0.65 at rest, 1.0 on tile hover/focus, and the `--accent-bright` glyph tint.
- **The hit box in px.** `getBoundingClientRect` reports zeroes throughout jsdom.
- **The flip as a screen reader announces it.** `aria-pressed` is asserted as an attribute and
  Chrome's AX tree gives `pressed: true`; how NVDA or VoiceOver *phrases* it is the epic checklist's.
- **The warm/cold `?face=` race.** jsdom loads no images and fires no `load`/`error`.
- **The tile caption / face-name divergence (Q12).** The caption keeps the printing's combined name
  (`Marang River Regent // Coil and Catch`) while the art shows one face; the panel's heading
  follows the face. Confirmed on screen; goes on the epic manual-testing checklist.

#### Epic manual-testing checklist entries this story adds

1. **The flip as a screen reader announces it** — "Flip card, toggle button, pressed" and how the
   tile's name reads immediately before it, on NVDA and VoiceOver.
2. **The caption/face-name divergence (Q12)** — with a DFC showing its back, the tile still says
   the combined name while the panel says the face's. Deliberate; check it does not read as a bug.
3. **The 2,166 reversible-art printings** — 0 are in any live deck, but a reviewer browsing the
   corpus will meet them first: flipping one shows a second painting of the *same* card, which is
   correct and reads as a bug from a screenshot.
4. **The cold-open tail with the sweep** — the +1.2 s measured above, on a real network rather than
   loopback.
5. **Flip controls materialising mid-Tab-traverse (AC 1's residue, keyboard half — review
   2026-08-06).** During the cold-open sweep (~1 s on the largest deck) a keyboard user who starts
   Tabbing immediately meets Tab stops appearing behind and ahead of them as records land — the
   same materialisation Q1 priced against the lazy option, compressed into the sweep window.
   Check it does not strand or skip focus on a real cold open with the keyboard.

### File List

**New (10)**

- `ui/src/state/faces.ts`
- `ui/src/state/faces.test.ts`
- `ui/src/containers/imagedFaces.ts`
- `ui/src/containers/useCardArt.test.ts`
- `ui/src/containers/FlipControl/FlipControl.tsx`
- `ui/src/containers/FlipControl/FlipControl.test.tsx`
- `ui/src/containers/FlipControl/FlipControl.css`
- `ui/src/containers/FlipControl/copy.ts`
- `src/companion/app/static/assets/index-BGgXI1GD.js` (built)
- `src/companion/app/static/assets/index-BW68s5aK.css` (built)

**Modified (14 source + 2 built + the mirror)**

- `ui/src/App.tsx`
- `ui/src/App.test.tsx`
- `ui/src/containers/CardTile/CardTile.tsx`
- `ui/src/containers/CardTile/CardTile.test.tsx`
- `ui/src/containers/CardTile/CardTile.css`
- `ui/src/containers/CardTile/imageUrl.ts`
- `ui/src/containers/CardDetail/CardDetail.tsx`
- `ui/src/containers/CardDetail/CardDetail.test.tsx`
- `ui/src/containers/useCardArt.ts`
- `ui/src/state/cards.ts`
- `ui/src/styles/tokens.css`
- `ui/tests/shell.test.ts`
- `ui/tests/store-writes.test.ts`
- `ui/tests/copy-rules.test.ts`
- `ui/tests/token-usage.test.ts`
- `src/companion/app/static/index.html` (built)
- `plugin/server/src/companion/app/static/**` (mirror, regenerated)

**Deleted (built, superseded)**

- `src/companion/app/static/assets/index-D9iRSKVH.js`
- `src/companion/app/static/assets/index-tvpYICK1.css`

**Not touched, deliberately:** `AppShell.tsx`, `CardGrid.tsx` (Q14), `src/api/**`, and all of
Python.

### Change Log

- **2026-08-06 — three-layer review, status `done`.** 21 raw findings → 2 decisions (both ruled:
  the sweep's no-re-sweep-while-`deck` window is ACCEPTED as the documented posture and ledgered
  with the extend-the-edge fix written down; AC 8's `<ul>` scaffold venue RATIFIED with the CDP
  eye-check as the grid-level half), 10 patches applied, 3 defers ledgered, 5 dismissed. The two
  substantive patches: the focus half of Q2's pop repair was missing — Tabbing from a tile to its
  own control un-scaled the frame and dropped `--shadow-raise`, the keyboard mirror of the exact
  pointer defect the frame was built to prevent — fixed as `:has(:focus-visible)` frame-wide with
  the tokens.css registration and the shipped-motion pin moved on the same selector text; and the
  preserve-3d scoping comment was measurably false — `transform-style` + the armed transition sat
  on all ninety-nine tiles while the comment claimed `[data-flipped]` scoped them — fixed by
  scoping both under the attribute-presence selector so the sentence became true. AC 9's rendered
  test was rewritten from a same-tile `quantity` re-render (which component-local state would
  have passed) to a real `boardsOf` re-render over new boards PLUS an unmount/remount, and
  `faces.test.ts`'s cross-reference to a nonexistent `FlipControl.test.tsx` test corrected. AC
  27's named shape-B probe was run at review (predicate weakened to `faces.length`): caught RED
  by five named tests, 5 failed / 1,250 passed, reverted. Record corrections: Q6's glyph is 18px
  not 16; `flipCard` guards with `Number.isInteger`, not the docstring's `Number.isFinite`; three
  more load-bearing comments (`FlipControl.css`'s rotation-location header, `CardTile`'s
  re-render mechanism, `useCardArt`'s `#`-encoding premise) corrected to say what the code does.
  AC 1's keyboard residue (controls materialising mid-Tab-traverse during the sweep) ledgered and
  added as epic manual-checklist entry 5. Gates re-run green: lint, format:check, `tsc -b
  --force`, `npm test` 1,255 / 50 files, build; bundle **JS 215,832 B (byte count unchanged, new
  hash `index-DmtAq_d6.js`), CSS 15,110 → 15,323 B (`index-DjIbf6Qz.css`, +213 B of focus/scoping
  selectors)**; `plugin/` mirror regenerated and verified byte-identical. Python untouched by
  every patch.
- **2026-08-06 — implemented, status `review`.** All fourteen questions answered before any code
  was written; eleven as proposed, three with stated deviations (Q1's sweep home and firing point,
  Q10's scoping of the back `<img>`, and the panel sharing the tile's 3D machinery). Task 0
  re-verified every corpus and deck number read-only — **all reproduce exactly** — and corrected
  two: the deck join is 1,999 rows rather than 2,027 (28 are orphaned by deck id), and Q10's
  back-face prefetch costs **1** extra image on `Prismatic Dragon`, not 10 (that deck has one
  flippable row beside nine faced-but-not ones). Q2 was decided by measurement rather than by the
  content model: React 19.2 warns about `<button>`-in-`<button>` in its **development build only**
  (`grep -c` over both react-dom builds gives 1 and 0), but the invalid nesting survives into the
  runtime tree, so the control became a **sibling** inside a new `.card-tile-frame` — with a
  cascade repair (`:where()`) that keeps every specificity in `CardTile.css` byte-identical.
  **Twelve evasion probes, two PASSED and both were real**: no fixture had a card with exactly one
  imaged face, and Q10's two-element design made Q7's `useCardArt` key change unobservable from
  either consumer. Both closed with named tests and recorded rather than quietly fixed. The
  eye-check ran in headless Chrome over CDP against the live backend across three decks and both
  motion settings — 28×28 disc, 32×32 hit box, 8/8 inset with the badge not overlapping, the Tab
  stop immediately after its own tile, `Flip card | pressed: true` from Chrome's own AX tree, and
  the reduced-motion fallback swapping faces by `visibility` with `transform: none` on both
  rotations. **One claim of mine was measured false and corrected in the source**: the sweep does
  not queue behind the images — it starts 6–10 ms ahead of them, and the cold-open tail roughly
  triples (**+1.2 s** on the 99-card deck) while first paint is untouched. Ten gates green;
  1,255 frontend (50 files); Python **2,501 passed / 1 skipped, unchanged**; bundle **JS 213,797 →
  215,832 B, CSS 13,452 → 15,110 B**, both changed as AC 30 requires, and the `plugin/` mirror
  regenerated to match.
- **2026-08-05 — created, status `ready-for-dev`.** Contexted off `bd72fc0` (PR #44 merged into
  `feat/companion-c4`). 32 acceptance criteria, 14 open questions, 6 inherited deferrals homed by
  name. Two structural blockers surfaced that no artefact records: the tile cannot know it has a
  back face without hydration (Q1), and the control's reserved home inside the tile's `<button>` is
  an interactive descendant the HTML content model bans (Q2). Corpus measured read-only: 2,778 of
  38,261 cards get a control, **every one with exactly two imaged faces** — which corrects the
  ledger's "a `[front, back]` destructuring is wrong for three real cards" (all three are split
  cards that get no control, and they are named). 42 of 2,027 live deck rows are flippable across 20
  of 40 decks; `Prismatic Dragon` renders AC 1 and AC 2 on one screen.

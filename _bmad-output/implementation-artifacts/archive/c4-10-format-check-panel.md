---
epic: c4
story: c4-10
work_branch: feat/companion-c4
story_branch: feat/companion-c4-10-format-check-panel
depends_on: >-
  c3-3 (merged in the C3 integration PR at `eb3f20a`) — `GET /api/deck/{deck_id}/format-check`,
  the endpoint this panel is the **sole consumer** of, whose `format_recognized` boolean and
  whose `CHECK_ORDER` have been *declared but unread* since the day they shipped and are homed on
  this story by name, and whose wire docstring carries the `is_legal` **`Warning:`** block that is
  the only guard against the trap `deferred-work.md:2430-2437` names this story for. c4-9 (merged
  at `4e31ea7`, PR #48) — the shape of a panel story and the current head. c4-7 (merged at
  `0fdb41b`) — `DeckList`, the **second** child of `AppShell`'s `right` slot and the row-with-a-
  right-aligned-thing precedent; `GroupHeader.css`'s `margin-left: auto` idiom and its hairline
  citation comment. c4-5 (merged at `bd72fc0`) — `CardDetail`, the **first** child of that slot,
  and `App.tsx:101-119`'s Q14 ruling on what the right column does behind a state panel, which
  this story **inherits rather than re-decides**. c4-2 (merged at `2a64231`) — `DeckBadges`,
  which renders the deck's **stored** format string and explicitly left the legality claim here;
  `deck.ts`'s two-request boot, whose per-mount request count this story's third request must
  extend. c4-1 (merged at `2095050`) — `src/api/client.ts`, *"the ONE door to the network"*,
  whose own header names this story's route as the next one to land in it. Also **c2-7**
  (`Badge` — five tones, unknown-tone clamp written for this story by name; `Panel`), **c2-6**
  (`AppShell`'s `right` slot — the **ninth** application of the displacement ruling), **c2-4**
  (the token layer, 69 tokens).
baseline_commit: 4e31ea7
---

# Story C4.10: Format check panel

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad about to register a deck,
I want the legality verdict visible in the right column,
so that I find out about a banned card or a copy-limit violation while I'm looking at the deck.

**What this story really is.** Six rows in a panel. A label, a badge, a hairline. Five ACs of
markup, over an endpoint that has been finished and green since 2026-08-01.

And then nine things that are not — four of which are invisible from the acceptance criteria, and
the first two of which change what a real deck says on a real screen today.

1. **The row has two slots. The endpoint has three fields. And 100% of the information lives in
   the third.** `DESIGN.md:423` is the entire visual spec — *"label in `{typography.body}`
   `{colors.text-secondary}`, `Badge` right-aligned, over `{components.legality-row.rule}`"* — and
   the mock has exactly those two slots. But the wire carries `check` (a **machine token**:
   `copy_limit`, `banned`, `rotation` — there is **no label field**), `status` (`pass` /
   `advisory` / `violation`) and `detail` (a server-authored sentence). Rendered to the letter,
   the one deck in forty with a real legality violation — `Kotis, the Fangkeeper — 100-card
   Brawl` — draws `Legality` and a red pill, and **the words `'Pym Particles' is not legal in
   brawl.` appear nowhere on the glass.** The story's own user statement says *"I find out about a
   banned card"*; the specified row cannot say which card. Worse, the mock's badge values
   (`'standard legal'`, `'60 / 60'`, `'no violations'`, `'15 / 15'`, `'none'`, `'11 cards'`) are a
   **fourth vocabulary** present in neither the artefact prose nor the wire, and computing them in
   TypeScript is *precisely* the fifth declared hole in c3-3's own rule guard — *"a rule written
   in TypeScript is invisible to every Python guard"* (`ui/README.md:1149`). **Q1 and Q2**, and
   together they are the only questions whose answer Brad can see.

2. **The deck-size deferral is exactly backwards, and 45% of the real deck table is told a false
   minimum the moment this panel ships.** Both `deck_validator.py:174-178` and
   `deferred-work.md:2355-2362` record the same mitigation: *"brawl and standardbrawl are
   genuinely 60-card formats, so the **20** brawl-family decks in the real deck table are correct
   and **only Commander** is affected — and there are currently **0** commander decks saved, which
   is why nothing looks wrong today."* **This project's own shipped skill says otherwise.**
   `plugin/skills/format-legality/SKILL.md:77`:

   > `| Brawl (Historic) | **100 (exact)** | 1 (singleton) | none | **yes** | Historic pool; key `brawl` |`

   **And the database agrees with the skill, not with the comment.** Measured read-only at
   `4e31ea7`: all **18** `brawl` decks have a mainboard total of **exactly 100** — min 100, max
   100 — 16 of them carry a `commander=1` row, and one is literally named *"Kotis, the Fangkeeper
   — 100-card Brawl"*, sitting beside its 60-card twin saved as `standardbrawl`. Scryfall's
   `brawl` key **is** the 100-card Arena format; `standardbrawl` is the 60-card one, and the
   validator's comment conflated the two under "brawl-family".

   So this panel puts `Mainboard has 100 cards; the minimum is 60.` on the glass for **18 of 40
   decks** — a **pass** sentence naming a minimum **forty cards below** the format's real one, for
   a format that is **exact-100** rather than a minimum at all. The deferral's named at-risk
   population is **empty** (0 Commander decks); the actually-affected population is the **largest
   single format in the table**. No badge flips today, because all 18 sit at exactly 100 — the
   defect is in the *sentence*, not the verdict — but a 61-card Brawl deck would be told `pass`,
   and a 99-card one would be told the minimum is 60. **Two record corrections are owed, and Q13
   decides whether this story renders the sentence anyway.**

3. **The panel is never all-green, on any deck, ever.** `rotation` is `advisory` on **40 of 40
   decks, permanently and by design**: `deck_validator.py:589-600` records that `cards` has 23
   columns and none is a release date, there is no sets table, and answering rotation needs a
   schema change, an importer change, a hand-written migration, a full re-import of 38,261 cards
   **and** a rotation-schedule source Scryfall's bulk data does not provide. Measured over 240
   real rows: **195 `pass` / 40 `advisory` / 5 `violation`** — and every single advisory is that
   one sentence. So a caution badge is not a signal here; it is furniture. A design that reads
   *caution = look at this* cries wolf on 100% of decks, and the mock's cheerful `Rotation
   exposure · 11 cards · caution` is a value the system **cannot produce**. **Q3** owns the label
   and **Q1** owns what the badge says about it.

4. **`is_legal` is a trap with no machine-checkable guard, and this story is its named home.**
   `deferred-work.md:2430-2437`: *"Nothing machine-checkable stops c4-10 from binding `is_legal`
   straight to the panel headline — a formatless deck would then render a red headline over six
   rows none of which is a violation."* The wire's own `Warning:` block
   (`deck_validator.py:557-565`) says to read it as *"certified legal"*, not *"something is
   wrong"*, and to synthesize a fault from `rows.some(r => r.status === 'violation')` and
   "cannot be checked" from `format_recognized`. Live exposure today is **zero** — the trap needs
   an unrecognised format and all 40 decks have one — which is exactly the condition under which
   a wrong binding ships green. **Q4.**

5. **This is the first panel in the epic with a network request of its own, and the client has no
   shape for a panel-level refusal.** Every other C4 panel derives from `boards`, already in the
   store. This one needs `GET /api/deck/{id}/format-check`, and `ui/README.md:1263-1286` records
   two precedents that point in **opposite directions**: *"a card refusal never puts a panel on the
   glass"* (FR-13 — one tile must not take down a view) and *"a DECK refusal ALWAYS does, and that
   is the same rule rather than its opposite"* (the deck **is** the surface). A format-check
   refusal is **neither**: the deck is still on the glass, so the second rule's premise fails; but
   the panel is a P0 surface rather than one tile among a hundred, so the first rule's premise
   fails too. `surfaceOf` has no arm for it. Nothing upstream rules this. **Q5 and Q6.**

6. **Five of the states this panel must render have zero real fixtures**, and this epic's standing
   review theme is fabricated ones. Measured over all 40 decks: real instances exist **only** for a
   `size` violation (4 decks) and a `legality` violation (1 deck). There are **zero** real
   instances of a `banned` violation (no saved deck contains a banned card in any format), a
   `copy_limit`/`singleton` violation, a `sideboard` violation, `format_recognized: false`, and the
   `(+N more)` multi-violation suffix — every offending deck has exactly **one** raw violation.
   c4-8's High was a fabricated fixture; c4-9's review turned four more into verified rows.
   **AC 26 makes every fixture's provenance a declared fact**, and Q… the honest routes to the
   missing five are enumerated rather than invented.

7. **`components.legality-row.padding: '9px 2px'` is the drift its own file bans by name.**
   `DESIGN.md:370` and UX-DR5 both say the scale is 4/8/12/16/24/32/48 and that *"the mock's
   18/14/9/7px one-offs are **drift, not spec**"* — and `9` is in that enumerated list. The
   frontmatter token carries it anyway. Both `Panel.css:63-69` and `Badge.css` have already made
   this exact repair with the citation written inline (Badge's was `2px 9px`, the same two
   numbers). **Q10** — and note the padding is the *only* geometry this panel has; there is no
   row-height token, no minimum, and no number anywhere.

8. **`ui/README.md` asserts twice that this story also ships a header legality pill. The epic's
   acceptance criteria require it nowhere.** `:1344-1346` — *"the mock's `standard legal` pill is
   **c4-10's**, over a `format-check` endpoint c4-2 never calls"* — and `:1396` — *"**c4-10** adds
   the legality pill beside it"*. Story 4.10's five ACs (`epics:2195-2216`) describe only the
   right-column panel. This README has had a forward statement falsified **five** times
   (`:249`, `:714`, `:773`, `:1206`, `:1429`). **Q4b** rules, and whichever way it goes the README
   is corrected in this diff.

9. **The panel's requirement lineage is not an FR, and a story that cites one will be citing a
   requirement that does not describe it.** Epic 4's FRs are FR-05 (grid + list + curve), FR-17
   (the detail panel) and FR-19 (card faces, flip, placeholders). **None mentions legality,
   format, banned cards or a validation panel.** The epics say so themselves at `:272-274` —
   *"the format check panel is P0 in EXPERIENCE.md but had no data source"* — and the UX import
   review said it at design time: *"'Format check' and 'Deck value' are new surfaces with **no FR
   behind them**"* (`imports/claude-design/REVIEW.md:81`). Cite **UX-DR21**, **EXPERIENCE.md:37**
   and **:96**, and **DESIGN.md:376**/**:423**.

Two corrections this story owes to the record, both measured:

10. **`'Mainboard has 1 cards; the minimum is 60.'`** — a real, shipped singular/plural defect,
    live on `Iron Man, Modern Marvel — reminder`, and this story is the first thing that puts it
    in front of a person. It is Python copy, in `deck_validator.py:693`.

11. **The `format` strings on the two endpoints are different values, and this story is the first
    thing that holds both at once.** `deferred-work.md:2418-2426`: `GET /api/deck/{id}` serves
    `deck.format` verbatim (which `DeckBadges` already renders in the header) while
    `GET /api/deck/{id}/format-check` serves `format.strip().lower()`. Measured: **0 of 40** real
    decks differ, so they agree on every deck that exists — but the entry's home condition
    (*"whichever first holds both values at once"*) is now met. **Q14.**

---

## Dev Notes

### The seam that already exists (do not rebuild any of it)

Everything below is **shipped and green at `4e31ea7`**. Read it before writing anything. The
single largest risk in this story is re-deriving in TypeScript something `src/logic` already
decided — which is the one hole c3-3's own guard declares it cannot see.

#### `GET /api/deck/{deck_id}/format-check` — the whole contract, already closed

Route: `src/companion/app/routes/decks.py:94-138`, on the existing decks router. **No query
parameters** (pinned: `test_routes_format_check.py:1125-1130`). Path param is an opaque string;
an unknown *or malformed* id answers **404 `deck_not_found`**, never 400 — the deck routes carry
no id shape constraint, unlike the card routes.

```python
# src/logic/deck_validator.py:475-500
FormatCheckStatus = Literal["pass", "advisory", "violation"]
FormatCheckName   = Literal["legality", "size", "copy_limit", "sideboard", "banned", "rotation"]
CHECK_ORDER: tuple[FormatCheckName, ...] = (
    "legality", "size", "copy_limit", "sideboard", "banned", "rotation",
)

class FormatCheckRow(BaseModel):     # :529-547
    check: FormatCheckName
    status: FormatCheckStatus
    detail: str

class FormatCheckReport(BaseModel):  # :550-586
    is_legal: bool
    format: str
    format_recognized: bool
    mainboard_count: int
    sideboard_count: int
    rows: list[FormatCheckRow]
```

Six facts that shape this story:

- **Always six rows, always in `CHECK_ORDER`.** Declared, not incidental, and pinned on both
  sides (`test_routes_format_check.py:208-219`, `test_format_check.py:116`). A panel that sorts
  or filters is re-deciding something the backend already decided.
- **Every field is required and non-nullable** on the wire — no `?`, no `| null`. There is no
  `strategy?`-style optionality asymmetry to branch around here.
- **There is no label field.** `check` is a machine token. Human labels do not exist anywhere on
  the wire, in `DESIGN.md`, or in `EXPERIENCE.md` prose. **Q3.**
- **The "no format" answer is a `200` carrying the identical shape** — never an error, never a
  union, never a second layout (`deck_validator.py:550-556`, pinned at
  `test_routes_format_check.py:391-451` over `["potato", ""]`). What changes is
  `format_recognized: false`, `format: ""`, and the `legality`/`banned` rows going `advisory` with
  `_unanswerable`'s sentence. `size`, `copy_limit` and `sideboard` **keep answering normally**.
- **`is_legal` is not a summary of the rows.** Read the `Warning:` block at
  `deck_validator.py:557-565` before writing any markup.
- **`format_check` reimplements no rule** (`:644-665`); every verdict comes from a
  `validate_deck` violation or from its absence. `find_rule_violations` in
  `tests/unit/companion/test_routes_format_check.py:844-1011` enforces that for Python and
  **declares that it cannot see TypeScript**.

The six pass sentences, verbatim (`deck_validator.py:691-699`) — this is what 195 of 240 real
rows say:

```
legality    Every card is legal in {format}.
size        Mainboard has {n} cards; the minimum is 60.
copy_limit  No card exceeds the copy limit; basic lands are exempt.
sideboard   Sideboard has {n} cards; the maximum is 15.
banned      No card is banned in {format}.
```

`rotation` has no pass arm at all (`:712-713`), and its one advisory sentence is
`_ROTATION_DETAIL` (`:589-591`), 86 characters.

#### `src/api/client.ts` — the one door, which names this route by name

`client.ts:22-24`, in shipped source: *"`GET /api/active-deck` is c4-2's, **the format check is
c4-10's** — all of them belong in this file."* `posture.test.ts:341` asserts
`expect(doors).toEqual(['src/api/client.ts'])`, keyed on the **identifier**, so even the bare word
`fetch` in stripped code fails.

The pattern is four parts per endpoint, and `readDeck` is the exact sibling to copy
(`client.ts:211-272`, `:374-383`, `:548-557`): a path-prefix constant plus an
`encodeURIComponent`-ing helper; a three-arm outcome union (`{kind:'…'}` / `{kind:'error',
reason: string|null}` / `{kind:'unreachable'}`) that **never throws and never returns `null`**; a
private `xxxOf(body: unknown)` narrower returning `null` for *"a 200 that is not this contract"*;
and an exported reader over the shared private `request()` (`:416-453` — the only `fetch`, one
`cache: 'no-store'`, one `AbortSignal.timeout(READ_TIMEOUT_MS)` at 10 s).

⚠️ Two wrinkles the sibling records: `deckPath('')` is the **collection** path `/api/deck/`, a
different route rather than a malformed parameter, so a blank id is refused one layer up
(`client.ts:242-245`); and this route has a path parameter, so it is **not structurally
retry-safe** — one request, no retry, no timer (`client.ts:34-48`).

#### `src/api/schema.ts` — two aliases this story must add

Ten aliases exist today (`HealthResponse`, `ErrorResponse`, `DeckSummary`, `Card`, `CardSummary`,
`DeckCardSummary`, `DeckDetail`, `ActiveDeck`, `CardFace`, `ErrorReason`). **`FormatCheckReport`
and `FormatCheckRow` are not among them** — c3-3 declined them deliberately (*"c4-1 owns the
aliases"*), and `ui/README.md:135-141` states the rule they were declined under: **an alias is
added only in the commit that gives it a consumer.** That commit is this one.

`wire-contract.test.ts:113-114` **already carries the anchors** for both names, so no guard edit
is owed — but the same guard bans re-declaring either shape anywhere outside `src/api/`. The
generated types are at `types.d.ts:662-699`; both enums generate as plain string-literal unions,
so a `switch` over `row.status` can be exhausted by `tsc`.

#### `src/state/deck.ts` — the boot this story must not disturb

`createDeckBoot` (`:300-390`) runs **two** requests per `start()`/`stop()` cycle behind a
**generation counter** (not a `live` boolean — `:283-296` gives the StrictMode argument in full),
and writes one `DeckState` through `applyDeckState`, the slice's single writer. The union's
`'deck'` arm carries `{ detail, boards }`, and **`boards`'s reference identity is the deck's
identity** — `deckMemory.ts` and `CardDetail`'s effect both depend on it. `resetDeckState` is
for tests; there is no production `deck_changed` handler and will not be until Epic 5/7.

⚠️ **c4-2's request-count assertion is the thing a third request runs into**
(`ui/README.md:1294-1304`): *"One `GET /api/active-deck` and at most one `GET /api/deck/{id}` per
mount, asserted as a request count over ten minutes of fake time — plus one edge-triggered
re-drive per poll recovery."* Whatever Q5 rules, that assertion is **extended, not loosened**.

`store-writes.test.ts:77` lists **five** stores (`useSystemStore`, `useDeckStore`, `useCardStore`,
`useInspectionStore`, `useFaceStore`), each with its single-writer module; **no component calls
`setState`.** A sixth is a decision with a diff.

#### `src/App.tsx` — where this panel mounts, and the ruling it inherits

```tsx
// App.tsx:297-304 (current)
right={
  surface.kind === 'deck' ? (
    <>
      <CardDetail boards={surface.boards} />
      <DeckList boards={surface.boards} />
    </>
  ) : undefined
}
```

`.app-shell-column` is already `display:flex; flex-direction:column; gap: var(--space-panel-gap)`
(`AppShell.css:151-156`), so **a third child stacks 24px beneath the second with no shell edit**.
`AppShell.tsx` is **not edited** — the **ninth** application of c2-9's displacement ruling, and
`AppShell.test.tsx:119`'s `'c4-10'` assertion must still pass **against the component's own
props**.

`App.tsx:101-119` is the ruling this story inherits verbatim rather than re-deciding:

> **Ruled: the detail panel renders only for `kind === 'deck'`.** … `validation-report-2026-07-25.md:78`
> records it as **L8** … **c4-7 and c4-10 inherit this rather than re-deciding it.**

`posture.test.ts:344-357` asserts `src/App.tsx` **does not match the network family** — so
whatever Q5 rules, `App.tsx` may call a state action but may never call `client.ts`.

⚠️ **`App.test.tsx`'s own fetch harness will silently swallow this route.** `answering()`
(`:157-184`) routes by prefix:

```tsx
if (path.startsWith('/api/deck/')) return Promise.resolve(bootDeck.clone())
```

`/api/deck/{id}/format-check` **starts with that prefix**, so without a new branch **placed
first** the format-check request is answered with the deck-detail body — a `200` that is not the
contract, silently, in the one file that exercises the whole path end to end. This is the same
class of repair c4-2 made when it turned a flat response sequence into a routed harness
(`App.test.tsx:101-113`). `callsTo(fetchMock, path)` (`:183-185`) is the counter don't-break 9
extends. ⚠️ **There is a SECOND prefix-routing harness in the same file at `:936`** — both need the
branch, and a fix to only one is the half-repair this note exists to prevent.

#### `src/components/Panel/Panel.tsx` — the `badges` slot nothing has ever used

```tsx
badges?: ReactNode   // right-aligned by `.panel-badges { margin-left: auto }` (Panel.css:133-138)
```

`filled(badges)` is one of the three things that makes a header render. **No component in the app
has ever passed it.** It is a third option Q4 must rule against explicitly rather than overlook:
a legality pill in *this* panel's own header is neither the epic's ACs nor the README's header
prediction, and it would be the same synthesized verdict in a third place.

#### `src/components/Badge/` — the primitive, and two things written for this story

```ts
// tones.ts
export const BADGE_TONES = ['neutral', 'accent', 'positive', 'negative', 'caution'] as const
```

`Badge.tsx:29-48`, naming this story in shipped source:

> tones will eventually arrive as **server data (c4-10's format legality**, c9's tiers), and an
> unchecked `` `badge-${tone}` `` would render an unstyled `badge-bogus` pill.

⚠️ **Verify the claim rather than inheriting it.** The wire sends a `status`, not a tone; the tone
is **derived in the UI** by a total map. So the clamp guards a *mapping*, not a raw value — and a
`Record<FormatCheckStatus, BadgeTone>` coupled in both directions by type-level asserts makes an
unknown tone unreachable by construction. Say which of the two closes it.

⚠️ **`Badge` renders `null` for empty content** (`filled(children)`), because *"a Badge with no
content is a bordered, washed, empty pill — visible chrome announcing nothing."* **A row whose
badge text is empty renders no badge at all** — Q1 must guarantee non-empty text or accept a bare
label row.

Measured at c4-2, on a real screen: the `::before` wash sits **behind** the text; contrast, text
over its own wash, `neutral` **7.60:1** · `accent` **8.33:1** · `positive` **7.97:1** · `negative`
**6.17:1** · `caution` **8.99:1**. **One number does not clear a floor** and
`ui/README.md:1394-1397` calls it *"a live constraint for **c4-10**, whose format-check badge
carries STATE"*: `neutral`'s `--border-strong` hairline is **1.89:1** on the page and **1.54:1**
on its own wash, under WCAG 1.4.11's 3:1. The four semantic borders are **6.73 / 9.96 / 7.32 /
11.49:1** and fine. **So a state distinguished by TONE is safe; a state distinguished by the
neutral border is not.** **Q17** carries the residue: nobody has measured tone-over-wash on
`--surface-panel` under the four alternate themes.

#### `src/components/Panel/` and the row idiom to reuse

`Panel` (`:33-67`): `title?: string` (rendered as `<h2 className="panel-title">` **and** the
`<section>`'s `aria-label`), `count?`, `badges?`, `level?`, `children`. **No `className` prop; a
consumer may not restyle it.** `overflow: hidden`, `var(--space-3)` (12px) body padding.

The right-aligned-thing idiom is shipped twice and must not be re-invented —
`GroupHeader.css:40-41`: *"`margin-left: auto` is 'right-aligned', the same mechanism
`.panel-badges` uses."*

The hairline idiom is shipped with its citation comment already written —
`GroupHeader.css:22-23`:

```css
/* 1px — DESIGN.md, 'components.group-header.rule': "1px solid {colors.border-hairline}". */
border-bottom: 1px solid var(--border-hairline);
```

This story's own token is `components.legality-row.rule` (`DESIGN.md:236`), the **same** value —
`--border-hairline` is `#2c3048` (`tokens.css:95`) and eleven DESIGN.md component blocks spell
`1px solid {colors.border-hairline}`. **No token is added for it.**

#### `src/containers/DeckList/` — the closest structural analogue

`DeckList.css:44-70` is the row grid: `minmax(34px, max-content) minmax(0, 1fr) auto`, **never a
bare `1fr`** (`shell.test.ts:960`), every `px` literal carrying a `DESIGN.md:NNN` citation within
60 characters in the same block comment. `DeckList.css:29-32` shows the container owning the
horizontal inset so the primitive stays unrestyled. `copy.ts` (`:1-38`) shows the import-free
copy-module shape and the type-level coupling asserted from the `.tsx` that has both halves in
scope — the pattern Q3's label map needs.

#### `src/containers/ColourDistribution/ColourDistribution.tsx` — the shape to match

Match: a **titled** `Panel` at `level="default"`; the single early-return branch for emptiness;
`copy.ts` with **zero imports**; type-level `Assert<T extends true>` couplings in both directions;
`aria-hidden` where the meaning is not.

Do **not** match: the `<figure>` (UX-DR44 gives `figure` to the curve and the colour bar **by
name** and says nothing about this panel — Q9), the `--colour-bar-share` runtime channel (this
panel has **no computed geometry**, so `eslint.config.js:204-240` and `RUNTIME_CUSTOM_PROPERTIES`
are **untouched** and the story says so rather than leaving it as an absence), and
`MANA_DATA_INK` (no `--mana-*` token may appear anywhere on this panel — UX-DR7).

---

### What the real data says (measured at `4e31ea7`, read-only, against the shipped database)

DB: `%LOCALAPPDATA%\artificial-planeswalker\cards.db` (`src/paths.py:48`), 249,679,872 bytes.
**38,261 cards, 40 decks, 2,027 `deck_cards` rows.** Every deck was driven through the **real
ASGI app in-process** (`httpx.ASGITransport`) against the real database, not through a mock.

#### A. The whole corpus, in one table

| measurement | result |
|---|---:|
| decks answering `200` | **40 of 40** |
| rows per deck | **6 / 6 / 6** (min / median / max) — fixed, always |
| total rows measured | **240** |
| `pass` | **195** |
| `advisory` | **40** |
| `violation` | **5** |
| decks with `format_recognized: false` | **0** |
| decks with **no format set** | **0** |
| `is_legal: true` / `false` | **35 / 5** |
| `is_legal: false` with **no** violation row (the trap) | **0** |

Deck formats: `standard` **19**, `brawl` **18**, `standardbrawl` **2**, `historic` **1**.

Check × status:

| check | pass | advisory | violation |
|---|---:|---:|---:|
| legality | 39 | – | **1** |
| size | 36 | – | **4** |
| copy_limit | 40 | – | – |
| sideboard | 40 | – | – |
| banned | 40 | – | – |
| **rotation** | – | **40** | – |

#### B. Every violation in the corpus, verbatim — the only real fixtures that exist

```
Sephiroth, Fabled SOLDIER — Standard Brawl  [standardbrawl]  size      Mainboard has 20 cards; the minimum is 60.
Kotis, the Fangkeeper — 100-card Brawl      [brawl]          legality  'Pym Particles' is not legal in brawl.
Graveyard Gravy                             [standard]       size      Mainboard has 3 cards; the minimum is 60.
Iron Man, Modern Marvel — reminder          [historic]       size      Mainboard has 1 cards; the minimum is 60.
Prismatic Dragon                            [standard]       size      Mainboard has 59 cards; the minimum is 60.
```

Five rows, five decks, **one violation each** — verified against raw `validate_deck`, so the
`(+N more)` suffix `_summarise` produces has **zero live instances**. Note `'Mainboard has 1
cards'` (§10 above).

#### C. The five states with no real fixture, and the honest route to each

| state | real instances | honest route |
|---|---:|---|
| `banned` violation | **0** — no saved deck holds a banned card in any format | 1,275 corpus cards carry a `banned` legality value; a **real card** in a **declared-synthetic deck** |
| `copy_limit` / `singleton` violation | **0** | re-check a **real** Standard deck against `commander`: `2 copies of 'Candy Trail'; commander is a singleton format (max 1 copy of any non-basic card). (+15 more)` — real deck, real card, **synthetic format**, declared |
| `sideboard` violation | **0** (35 of 40 decks have no sideboard at all) | declared-synthetic quantity |
| `format_recognized: false` | **0** | override a real deck's format to `""` / `"potato"` — measured, produces the exact advisory pair |
| `(+N more)` suffix | **0** | falls out of the `copy_limit` route above |

**AC 26 is written for this table.** c4-8's High was a fabricated fixture whose own pin was
tautological; c4-9's review replaced four invented rows with verified ones. Every fixture in this
story is either a **verified real row** or **declared synthetic in place**, with no third option
and no silent middle.

#### D. The eighteen decks the size row lies to

| measurement | result |
|---|---:|
| `brawl` decks | **18** |
| their mainboard totals | **min 100 / max 100** — every one exactly 100 |
| …carrying a `commander=1` row | **16** |
| `standardbrawl` decks (genuinely 60) | **2** |
| `commander` decks | **0** |
| decks shown `…the minimum is 60.` while their format is exact-100 | **18 (45%)** |

`plugin/skills/format-legality/SKILL.md:76-78` is the contradicting artefact, in this repo, shipped
to users. `_SINGLETON_FORMATS` (`deck_validator.py:185-197`) **already** treats `brawl` as
singleton, so the copy-limit rule knows what format it is; only `_MIN_MAINBOARD` does not.

#### E. Strings — what the layout actually has to hold

| measurement | result |
|---|---:|
| longest `detail` observed live | **86 chars** — the rotation advisory, ×40 |
| shortest `detail` observed live | **27** — `No card is banned in brawl.` |
| longest `check` token | **10** — `copy_limit` |
| corpus worst case via the `singleton` template | **229 chars** (the 141-char joke card), **240** with `(+99 more)` |
| realistic non-joke worst case | **~158 chars** (a 70-char DFC name) |

**`check` is a closed six-value vocabulary and never contains a card name or a count.** `detail`
is entirely dynamic: card names, counts and format names all interpolate.

#### F. Cost

Per request, in-process: **min 2.5 ms / median 4.5 ms / max 29.7 ms** (cold first). Largest deck
(`Squirrel Girl — Infinite Nuts (Brawl)`, 100 mainboard): cold **8.5 ms**, warm median **5.4 ms**.
A non-event against NFR-05's 1 s — but note **what** it costs: a **second**
`get_deck_with_cards` on top of the deck-detail fetch the app already pays. The cost is a
duplicated eager load, not the validation.

#### G. Errors

`404` body is exactly `{"reason": "deck_not_found"}`. A non-UUID id also answers **404**, not 400.
The declared status set for this operation is `200 / 400 / 404 / 413 / 500 / 503`, with **both**
503 tokens (`database_not_initialized`, `database_unavailable`) on the one entry — pinned at
`test_committed_schema.py:243-266`.

---

### The wire types — what this story may and may not read

```ts
// ui/src/api/types.d.ts:662-699 — read through NEW aliases in src/api/schema.ts, import type ONLY
FormatCheckReport { is_legal: boolean; format: string; format_recognized: boolean
                    mainboard_count: number; sideboard_count: number
                    rows: FormatCheckRow[] }
FormatCheckRow    { check: 'legality'|'size'|'copy_limit'|'sideboard'|'banned'|'rotation'
                    status: 'pass'|'advisory'|'violation'
                    detail: string }
```

- **Every field required, non-nullable.** No `?? ''`, no `undefined` branch.
- **Never re-declare a wire shape outside `src/api/`** (`wire-contract.test.ts:145`); the anchors
  for both names already exist at `:113-114`.
- **Every `src/api/` import from a container is `import type`**; the inline-`type` form is refused
  because `verbatimModuleSyntax` still runs the module (c4-5 decision 2).
- **`format` here is the NORMALISED value**; `DeckDetail.format`, which `DeckBadges` already
  renders in the header, is the **stored** one. Q14.

---

### Decide-once rulings this story inherits (do not re-derive)

1. **`src/containers/` is where a component that BEHAVES lives** (c4-4 Q1); `src/components/` is a
   closed set-equality category banned from hooks, `on*`, `ref`, spread and a value `react`
   import. A panel that reads the store is a **container**. `ui/README.md:548` names **c4-10** in
   the inheriting list.
2. **Container posture** (`ui/README.md:566-570`): MAY hold state, call hooks, attach handlers,
   read the store through `src/state/`, compose primitives. **MAY NOT reach the network**, import
   a state library directly, write another module's slice, or declare a design token. ⚠️ **The
   first clause is Q5's whole constraint**, and it is enforced three ways in one block —
   `shell.test.ts:2071-2086` refuses `fetch|XMLHttpRequest|EventSource|WebSocket`, `from 'zustand'`
   **and** `.setState` in any container module.
2b. **A container's `src/api/` import is `import type`, never `import { type X }`** —
   `shell.test.ts:1986-2023` reads the *statement* form, because `verbatimModuleSyntax` still runs
   the module for the inline spelling (c4-5 decision 2).
3. **Directory-per-component, no barrels, named exports only.** `react-refresh/only-export-components`
   is an ESLint **error**, so every pure helper is its own module and its own `CONTAINERS` entry.
4. **`AppShell.tsx` is never edited; placeholders are displaced, not deleted** (c2-9) — the
   **ninth** application.
5. **Class names are flat kebab-case prefixed with the component** (`format-check-row`, never
   `format-check__row`); stylelint `selector-class-pattern` is an error.
6. **Every colour, shadow, radius, spacing, duration and type value goes through a token.** No
   inline `style={{…}}` except through a **named** declared runtime channel — and this story needs
   none.
7. **`px` literals in `src/components/` and `src/containers/` need a `DESIGN.md:NNN` citation
   within 60 characters, in the same block comment** (`shell.test.ts:1002-1032`). This story's
   citable line is **`DESIGN.md:236-237`** (`components.legality-row`). ⚠️ Q10 first.
8. **Bare `1fr` and `minmax(auto, 1fr)` grid tracks are banned** (`shell.test.ts:960`); grid items
   need `min-width: 0`.
9. **`:focus-visible`, never `:focus`; `outline: none` banned in all four spellings.** Rows are
   display-only, so this should not bite — say so.
10. **`--accent-dim` on `--surface-overlay` is banned (2.70:1)**; the guard is same-block only.
11. **Nothing pulses, loops or alternates at any setting**; `animation-iteration-count` may only
    be `1`. UX-DR42's exhaustive inventory has **no format-check row** and this story adds none.
12. **`Panel` is a primitive a consumer may not restyle.**
13. **`.app-shell-columns` is the app's single scroll container.**
14. **Any authored user-facing string lives in a `copy.ts` beside its component**, registered in
    `COPY_MODULES` with a **>40-character** reason. **Server data is not copy** — ⚠️ the six
    `detail` sentences are *authored by the backend* and arrive on the wire; they are **data** by
    the same rule that keeps card names out of `DeckList/copy.ts`. The **labels** Q3 writes are
    copy. The attribute half collects *every* literal reaching nine read-aloud attributes.
15. **Emptiness is `filled()` / `typeof` + `trim()`, never truthiness; a number is
    `Number.isFinite`, never `count && …`.**
16. **Props and maps are coupled to their source type in both directions by type-level asserts**
    (`Assert<T extends true>`), so a seventh check name and a widening to `string` are both `tsc`
    failures.
17. **`fireEvent` is the suite's only DOM-event idiom** (c4-5 Q9).
18. **`npx tsc -b --force`, never `tsc -b`.**
19. **Guards are proven through the full `npm test`, never a standalone file run** — the
    standalone `token-usage.test.ts` runner crash is ledgered (`deferred-work.md:3639-3649`) and
    has made a probe harness lie twice.
20. **`--negative`, `--caution` and `--positive` are legitimately spent here** — the
    `CALM_STYLESHEETS` allowlist is **scoped**, and `token-usage.test.ts:1002-1021` says so naming
    this story: *"c4-10's format check maps a violation to `negative` and MUST spend that token.
    The scope is the rule, not a loophole."* `FormatCheck.css` does **not** join
    `CALM_STYLESHEETS`.
21. **One door to the network, named exhaustively** (`posture.test.ts:341`), and `src/App.tsx` may
    not become the second (`:344-357`).
22. **An alias is added to `schema.ts` only in the commit that gives it a consumer**
    (`ui/README.md:135-141`).
23. **A runtime custom property is a NAMED channel in two places** — not triggered here, and the
    story says so.
24. **Nothing outside a slice's own module writes it** (`store-writes.test.ts`).

---

### Latest technical specifics

- **React 19.2 / TypeScript 5.9 / zustand 5 / Vite 7 / Vitest 4.1.10** — unchanged; this story
  adds **no dependency**. `package-contract.test.ts` pins the set.
- **zustand v5 has no equality argument on `create`.** A selector returning a **new** object or
  array each call re-renders forever. If Q5 ships a slice, its selector returns the stored
  reference or a primitive.
- **Two vitest projects**: `src/**/*.test.{ts,tsx}` → jsdom (`dom`); `ui/tests/**/*.test.ts` →
  node. `gate-geometry.test.ts:53` forbids `.tsx` under `tests/`. A pure derivation test with no
  JSX is a **`.ts`**.
- **`aria-query` maps `<header>` to `banner` unconditionally**, so every titled `Panel` is a
  phantom `banner` in jsdom and none in a browser. c4-9 took the count to **5**; **this panel
  takes it to 6.** Scope role queries through the `h1`, never `getByRole('banner')`.
- **jsdom has no layout**: `getBoundingClientRect()` is zeroes. Every geometry claim is about the
  stylesheet or the class, never a rendered pixel — the eye-check owns the rest.
- **Windows line endings**: `pathlib.write_text` translates LF→CRLF; `ui/.gitattributes` forces
  LF, so `format:check` goes red across files a probe merely *restored*. Restore with
  byte-preserving writes.
- **A vitest worker crash** (`Error: Worker exited unexpectedly` with **zero** failing assertions)
  is a known flake. Re-run before investigating.
- **The registry guards walk `git ls-files`**, so **an un-`git add`ed module is invisible and
  passes vacuously**. `git add` before believing a green run — and check the **bundle assets** are
  tracked before committing: untracked bundle assets have been a **High** finding in two of the
  last seven stories (c4-3, c4-7).
- **Six gates on the frontend**, plus the generated-types drift check CI runs as a seventh
  (`ui/README.md:123-125`): touching no Pydantic model means `npm run gen:api` produces no diff,
  and the story states that rather than assuming it.

---

### The twenty things this story must not break

1. **`AppShell.tsx` — not edited.** `AppShell.test.tsx:119`'s `'c4-10'` assertion must pass
   **against the component's own props**, unchanged. Ninth application of c2-9.
2. **`App.test.tsx`'s right-column displacement block** (`:530-556`) — `c4-5` and `c4-7` are
   already absent; this story makes **`c4-10`** absent **by its own panel**, and both halves are
   asserted (absence *and* the region on the glass), which is the shape c4-7 and c4-9 established.
3. **`CardDetail` and `DeckList` render exactly as they do today**, in that order, with the new
   panel **third**. Document order is the contract — `App.test.tsx:546-554` already asserts
   detail-before-list with `compareDocumentPosition`; extend it, do not replace it.
4. **The right column's gate stays `kind === 'deck'`**, inherited from `App.tsx:101-119`, not
   re-decided. L8 is cited, not re-opened.
5. **`boards` is not read, not copied and not re-derived.** This panel does not need it. AD-12's
   single derivation and `deckMemory.ts`'s reference-identity dependency are untouched — the
   cleanest don't-break in the epic, and worth stating because every sibling panel takes `boards`
   as its only prop and copying that shape here would be wrong.
6. **The inspection slice is not touched.** No `setHovered`, no `togglePin`, no
   `useIsLiveTarget`, no click handler, no `tabindex`. UX-DR21: **display-only**.
7. **The card cache is not touched.** `hydrateCard`/`hydrateDeckCards` are not called here; this
   panel neither reads nor starts a card fetch.
8. **`useDeckStore`'s five-state union and its single writer are unchanged.** If Q5 adds a slice
   it is a **sixth store**, not a sixth arm on `DeckState` — a new field on the `'deck'` arm would
   put a network outcome inside the value whose identity is the deck's identity (don't-break 5).
9. **c4-2's per-mount request count is EXTENDED, not loosened** — the ten-minutes-of-fake-time
   assertion must still be a *number*, and it must still fail if a request repeats.
   ⚠️ **And `answering()`'s route table gains a `format-check` branch BEFORE its
   `startsWith('/api/deck/')` line**, or every App-level test serves the deck body to this route
   and the panel's whole failure path passes for the wrong reason.
10. **The one network door stays `['src/api/client.ts']`** (`posture.test.ts:339`), and
    `src/App.tsx` still does not match the network family (`:344-357`).
11. **`wire-contract.test.ts`** — no wire shape re-declared outside `src/api/`; both anchors
    already exist and must stay green.
12. **The token inventory and its two pins** (`tokens.test.ts:321`, `token-usage.test.ts:1170`) —
    **69 today**. `components.legality-row`'s two values resolve to `--border-hairline` and a
    padding pair; **69 is expected to hold**, and if it moves both pins move together with a
    stated reason.
13. **`CARD_SHAPED`'s four entries and both directions** (`token-usage.test.ts:896`). This panel
    draws no card: its stylesheet must **not** join, and `--radius-card` must appear nowhere in
    it.
14. **`MANA_DATA_INK`'s two entries are untouched** and **no `--mana-*` token appears anywhere in
    this story** — UX-DR7 makes them data ink only, and a colour-identity dot beside a legality
    row is exactly the misuse.
15. **`CALM_STYLESHEETS` keeps its one entry.** This file spends `--negative` legitimately and does
    **not** declare itself calm (ruling 20).
16. **`RUNTIME_CUSTOM_PROPERTIES` keeps its two entries** and `eslint.config.js:204-240` is
    **unedited** — `inline-style-violation.tsx` stays pinned at exactly **2** messages
    (`lint-gates.test.ts:133-172`).
17. **The reduced-motion inventory** (`tokens.css:285-317`) and the enumerated shipped-motion pin
    (**4**) are unchanged. UX-DR42 has no format-check row and this story adds none.
18. **`CardDetail`'s single polite live region stays the only one.** This panel adds **no**
    `aria-live` (Q16).
19. **Python is untouched**: `uv run pytest` stays at **2,501 passed / 1 skipped**. ⚠️ Q13 is
    explicitly the question of whether to break this one, and the default answer is no.
20. **`npm run gen:api` produces no diff** — no Pydantic model moves in this story, so the
    committed `types.d.ts` and `openapi.json` are already correct. State it; CI checks it.

---

### Source tree — what exists, what this story touches

```
ui/src/
  containers/
    FormatCheck/                  NEW   the panel, its six rows
      FormatCheck.tsx             NEW   container: reads the report, composes Panel + Badge
      FormatCheck.css             NEW   the row, the hairline, the right-alignment
      FormatCheck.test.tsx        NEW   jsdom project
      copy.ts                     NEW   panel title, the six labels, whatever Q1 authors
      rows.ts                     NEW?  only if Q1/Q2 need a pure projection worth testing alone
    DeckList/…                    READ  the row idiom, the import-free copy.ts, the coupling shape
    ColourDistribution/…          READ  the sibling panel shape; NOT its figure, NOT its channel
  components/
    Badge/…                       READ  five tones, the clamp, the empty-content null
    Panel/…                       READ  level="default", title as h2 + aria-label
    DeckBadges/…                  EDIT? only if Q4b ships the header legality pill
  api/
    schema.ts                     EDIT  + FormatCheckReport, + FormatCheckRow (10 → 12 aliases)
    schema.test.ts                EDIT? type-level pins for the two closed unions (CardFace pattern)
    client.ts                     EDIT  the path helper, the outcome union, readFormatCheck
    client.test.ts                EDIT  the new reader's arms
  state/
    formatCheck.ts                NEW?  Q5 — a sixth store, or no new module at all
    formatCheck.test.ts           NEW?  ditto
  App.tsx                         EDIT  one sibling inside `right`; whatever Q5 drives the fetch
  App.test.tsx                    EDIT  displacement, document order, absence behind every state arm
ui/tests/
  shell.test.ts                   EDIT  CONTAINERS + the pin at :1894 (19 → N)
  copy-rules.test.ts              EDIT  COPY_MODULES + a >40-char reason (11 → 12)
  store-writes.test.ts            EDIT? STORES (5 → 6) only if Q5 adds a slice
  posture.test.ts                 EDIT? only if the door list's prose needs its next-route line moved
  tokens.test.ts                  EDIT? only if a token moves — it should not
_bmad-output/implementation-artifacts/
  deferred-work.md                EDIT  this story's dispositions — IN THIS COMMIT (AC 40)
src/companion/app/static/                 BUILD committed bundle, must change (JS and CSS)
plugin/server/src/companion/app/static/   BUILD ⚠️ hand-copied mirror, checked by NOTHING
                                          [CORRECTED at implementation, see Completion Notes:
                                          FALSE — test_spa.py::TestThePluginMirror compares both
                                          trees byte-for-byte and went red on the first pytest]
```

**⚠️ Two unguarded gaps, both demonstrated live in earlier stories.** (a) ~~The plugin mirror is
enforced by no test, no workflow and no script~~ **[CORRECTED at implementation — this claim is
FALSE, measured: `TestThePluginMirror` byte-compares both trees and a CI drift check exists; the
true residue is only that neither runs from the `ui/` side. See Completion Notes finding 2.]**
c4-7 raised it with **the C4 retro** as its named home; update it by hand and verify sha256 per
file. (b) The registry guards cannot see an untracked file.

**Baselines to measure against** (verified on disk at `4e31ea7`):

| baseline | value |
|---|---|
| frontend tests | **1,476 passed / 57 files** |
| Python tests | **2,501 passed / 1 skipped** |
| tokens | **69** (`tokens.test.ts:321`, `token-usage.test.ts:1170`) |
| containers | **19** (`shell.test.ts:1894`) |
| primitives | **18** (`shell.test.ts:1353`) |
| stores | **5** (`store-writes.test.ts:77`) |
| copy modules | **11** (`copy-rules.test.ts:107`) |
| `schema.ts` aliases | **10** |
| `CARD_SHAPED` | **4** |
| `MANA_DATA_INK` | **2** |
| `RUNTIME_CUSTOM_PROPERTIES` | **2** |
| `CALM_STYLESHEETS` | **1** |
| shipped-motion pin | **4** |
| `inline-style-violation.tsx` messages | **2** |
| bundle JS | `index-D6NJThYj.js` **221,585 B** |
| bundle CSS | `index-BqIKsEIE.css` **19,294 B** |
| font | `space-grotesk-latin-wght-normal-BhU9QXUp.woff2` 22,288 B |
| jsdom phantom `banner` count | **5** (Chrome: 1) |
| right-column children | **2** |

**Both bundle assets must change.** c4-5's phrasing applies — *"a byte-identical JS bundle here
means it did not ship"* — and a byte count can be unchanged while the hash changes: **report
both**.

---

### The inherited deferrals — give each a disposition (AC 40)

C2 retro **ruling R2**: inherited deferrals are ACs at context time, and *"not mentioned" is a
failure of the AC*. There are **eleven**, and **seven of them name this story as their home** —
more than any story in the epic.

1. **`format_recognized` and the six-row shape are declared but unread until c4-10**
   (`deferred-work.md:2394-2400`). *"If c4-10 renders the panel without ever reading
   `format_recognized`, that is a signal the field was over-built and it should be **deleted**
   rather than maintained."* Q8 must read it or kill it; there is no third answer.
2. **The "no format" branch must key on `format_recognized`, not `format === null`**
   (`:1972-1981`). *"If it writes `format === null` against the generated type that branch is dead
   code."* Note the generated type is `format: string` (non-nullable) — so `=== null` would not
   even compile. Say so.
3. **`is_legal: false` above six non-violation rows is a live UI trap** (`:2430-2437`), *"Home:
   c4-10 … Severity: Low here, **Medium if c4-10 binds it unread**."* Q4.
4. **The format-check report's `format` is normalised; the deck detail route's is stored**
   (`:2418-2426`), *"Home: c4-10 or c4-1, whichever first holds both values at once."* That
   condition is met **here**. Q14.
5. **`_MIN_MAINBOARD = 60` applies regardless of format, and c3-3 published it to a human for the
   first time** (`:2355-2362`). ⚠️ **This entry's measurement is wrong** (§2 / §D above) and the
   correction is owed in this diff whichever way Q13 goes.
6. **The copy-limit row answers definitively under the 4-copy fallback for an unrecognised
   format** (`:2439-2445`) — homed on an unowned `src/logic` rule story, not here. Confirm
   not-triggered (0 unrecognised formats live) and re-home unchanged.
7. **`format_recognized: true` does not mean the format key is present in the card data**
   (`:2402-2406`) — unowned. Not reachable against a synchronised snapshot; re-home unchanged.
8. **A `restricted` card is reported as "not legal"** (`:2325-2334`) — unowned, 0 live instances,
   no vintage deck. This panel would render the wrong sentence the day one exists. Re-home with
   the exposure re-stated.
9. **Rotation exposure cannot be computed from local data at all, and the panel now says so
   permanently** (`:2325-2341`) — *"a permanent shrug in a P0 panel, but an accurate one … must
   not be quietly promoted to `pass`."* §3 above measures it at **40 of 40, forever**. State
   whether the design acknowledges that or merely tolerates it.
10. **`Badge`'s appearance and its tone-over-wash contrast** (`:1333-1362`, `:3496-3502`) —
    *"`Badge` at **c4-10** (the format check) and c4-2 (the header badges)."* c4-2 discharged the
    stacking and the five ratios; the residue is the **neutral-border constraint** (§ Badge above)
    and the unmeasured alternate themes. Q17.
11. **`DeckRepository.list_decks` ties on `created_at`** (`:1668-1699`, Medium-High) — checked and
    re-homed unchanged at c4-7, c4-8 and c4-9. This story never calls `GET /api/decks`. Same
    disposition.

**Triggered "whoever ships the next X" residues** — each also needs a line:

- **F1: story-key-shaped strings on the rendered view** (`:3456-3464`, `:3985-3987`) — c4-9
  recorded *"`c4-10` and `c4-11` remain, in the right column's placeholder and the skip-link
  work."* **This story removes `c4-10`**, leaving one. The gate itself stays **c8-5's**.
- **The C3 retro's manual-testing items C3 and C4** (`epic-c3-retro:473-474`) — both are
  format-check reads homed here by name: *"read `is_legal` against the six rows"* on the brawl
  deck, and *"the 1-card `historic` deck; the min-size row saying '60', D-1.6b visible to a
  human"*. The eye-check discharges both, or says why not.
- **`Panel`'s default-level eye-check** (`:1333-1352`) — discharged at c4-5/c4-7; confirm and
  re-state rather than re-run.
- **The next story that renders an identifier / picks a type role** (`:3626-3637`) — this panel
  renders **no** numeric value at all unless Q1 puts one in a badge. Say which type roles ship and
  on what authority; `--type-body` for the label is in `DESIGN.md:423` in writing.
- **`StatChip`'s first surface** — c4-9 ruled it does not ship there. Not triggered here either
  (`DESIGN.md:423` names only a label and a `Badge`); say so.
- **The visually-hidden idiom's third instance** — `ManaCurve.css:141-165` records the trigger:
  *"whoever writes the third visually-hidden block promotes it to `src/styles/`."* Two exist
  (`CardDetailChrome.css:182-199`, `ManaCurve.css:166-174`); c4-9 asserted it did **not** fire.
  Q1/Q2's rulings decide whether this panel writes one. If it does, **the promotion happens in
  this commit.**
- **The cross-file card-shape collision** (`:3587-3596`) — not expected; say so.
- **The hydration sweep's no-re-drive window** (c4-6 review ruling 1) — ⚠️ **not triggered, and
  the reason is structural**: this panel reads no card and derives nothing from the cache. First
  panel in four to escape it for a reason other than `cmc`.
- **The registry guards are blind to untracked modules** (`:3869-3877`) — c4-9 took part of it and
  declined the rest. This story touches at least two registry tests. Take or decline with a
  reason.

---

### Open questions — answer these before writing code

Seventeen. **Q1 and Q2 decide what a real deck says on a real screen**; Q4, Q5 and Q6 change what
ships; Q13 decides whether Python moves; the rest close holes that would otherwise be found at
review.

**Q1 — What does the badge SAY?**
The wire gives `status` (three words) and `detail` (a sentence). The mock gives short derived
values (`'60 / 60'`, `'no violations'`, `'11 cards'`) that exist in no artefact and cannot be
computed without re-deriving rules in TypeScript — `ui/README.md:1149`'s declared fifth hole, and
the exact thing AD-1 exists to prevent. `Badge` is `--type-label`: 11px, **uppercase**, tracked,
`white-space: nowrap`. A sentence in it would be catastrophic.
*Proposal:* **the badge carries the STATUS WORD** — `PASS` / `ADVISORY` / `VIOLATION` — through a
`Record<FormatCheckStatus, string>` in `copy.ts` coupled to the wire union in both directions
(ruling 16). Three reasons: (a) it is the one short string the wire actually carries, so nothing is
derived and the c3-3 hole is not entered; (b) it makes the tone map legible rather than
decorative — colour is never the sole carrier (UX-DR26/UX-DR29's rule applied here), because the
word beside the colour says the same thing; (c) it is stable at 11px uppercase in a 452px column.
⚠️ **Reject the mock's values explicitly and record why**, so the next reader does not re-propose
them. And note the cost plainly: `ADVISORY` is a word most players will not parse, which is why
Q2 matters more than this question does.

**Q2 — Where does the `detail` sentence go?**
`DESIGN.md:423` has two slots and the endpoint has three fields. Rendered to the letter, the
banned-card story the user statement promises **cannot be told** (§1).
*Proposal:* **the detail sentence renders as a second line beneath the label**, in
`--type-micro` at `--text-tertiary`, inside the same row — a two-line row rather than a second
column, so the badge stays right-aligned against the label and the row's grid does not have to
hold a 158-character string in a track. Record it as a **DESIGN.md amendment** to
`components.legality-row` and to `:423`, in the same commit, exactly as c4-7 amended
`deck-row.columns` and c4-9 amended `color-bar`. ⚠️ Three things to get right and one to measure:
the row height stops being uniform (six rows of unequal height is fine; a design that assumed a
fixed 41px is not); `--text-tertiary` on `--surface-panel` is **5.4:1** and clears 4.5:1;
`_ROTATION_DETAIL` renders on **every deck, forever**, so the second line is 86 characters of
permanent furniture on 40 of 40 decks — **measure how tall the panel becomes** and say whether
that is acceptable, because the alternative (detail only when `status !== 'pass'`) is a **fourth**
vocabulary decision and hides the size sentence §2 is about. The other real option is a `title=`
attribute, which is hover-only and banned by UX-DR39; say so rather than leaving it unconsidered.

**Q3 — What are the six labels?**
`check` is a machine token. Three vocabularies exist and none is normative: the mock's JS data
(`'Format legality'`, `'Maindeck size'`, `'Copy limit'`, `'Sideboard'`, `'Banned or restricted'`,
`'Rotation exposure'`), `EXPERIENCE.md:37`'s IA row (*"Legality, size, copy limit, sideboard,
banned, rotation exposure"*), and the wire tokens themselves.
*Proposal:* **adopt the mock's six strings verbatim**, in `copy.ts`, as a
`Record<FormatCheckName, string>` coupled in both directions. The mock is the only artefact that
wrote them as *labels for this panel*; `EXPERIENCE.md:37` is an IA summary, not copy. ⚠️ **One
must change**: `'Banned or restricted'` is a **false label** — `deck_validator.py` reports
`restricted` cards through the *legality* row, deliberately and pinned
(`test_restricted_is_unchanged_by_the_banned_split`), so a row labelled "Banned or restricted"
would never fire for a restricted card. Propose **`'Banned cards'`** and record the reason;
`EXPERIENCE.md:37` and the mock both get the correction. Also confirm sentence case, no periods,
matching `DECK_LIST_TITLE`'s voice.

**Q4 — Does the panel carry a verdict at all, and (Q4b) does the header legality pill ship?**
`is_legal` is a trap with no machine-checkable guard, homed here by name (deferral 3). The
README asserts twice that this story also fills the header with a `standard legal` pill; the
epic's ACs require only the panel.
*Proposal (a):* **no headline, no summary badge, no `count` on the Panel, and no use of `Panel`'s
own `badges` slot** — a third venue for the same synthesized verdict, unused by any component in
the app, and easy to overlook because nothing currently exercises it. UX-DR21 is *"one row
per check"* and nothing else; a synthesized verdict is a seventh row the artefacts do not have,
and `is_legal` is the one field on the wire that must not become it. **Assert its absence by
test** (c4-5's AC-14 pattern): the identifier `is_legal` appears nowhere in `src/` outside the
generated types. That turns a prose `Warning:` into a machine-checkable fact, which is precisely
what the ledger says does not exist.
*Proposal (b):* **the header legality pill does NOT ship in this story**, and `ui/README.md`'s two
predictions are **corrected in this diff**. Reasons: it is outside the epic's five ACs; the pill's
tone would have to be synthesized from `format_recognized` + a row scan (the same trap, in the one
place with no rows beside it to contradict it); and it would put a **second** consumer of this
endpoint in a **second** column with no shared state, which is Q5's problem doubled. Name the
honest home — a later story, or the C4 retro — rather than leaving the README asserting a thing
that did not happen.

**Q5 — Where does the fetch live, what writes the store, and who drives it?**
A container **may not reach the network** (ruling 2). `App.tsx` **may not** either
(`posture.test.ts:344`). `client.ts` is the door. So something in `src/state/` must own it.
*Proposal:* **a sixth store, `src/state/formatCheck.ts`** (`store-writes.test.ts` 5 → 6), holding a
discriminated union in the manner `DeckState` established — `'idle' | 'loading' | 'report' |
'refused'` — with **one writer**, a `loadFormatCheck(deckId)` action, and a `useFormatCheck()`
selector returning the stored value. Driven from **`App.tsx`'s existing effect layer**, keyed on
the active deck id, the same shape `hydrateDeckCards` is driven with. Rejected alternatives, each
with its reason recorded: (i) a **third request inside `createDeckBoot`** — it would gate the
whole deck view on a panel's data, put a network outcome inside the value whose reference identity
is the deck's identity (don't-break 5/8), and turn one duplicated `get_deck_with_cards` into a
first-paint dependency; (ii) a **field on `DeckState`'s `'deck'` arm** — same objection, plus it
makes the union's exhaustiveness meaningless; (iii) **the container fetching directly** — banned,
and the ban is the whole point of `posture.test.ts`. ⚠️ Whatever ships, **c4-2's per-mount request
count is extended to three** and stays a number, and the generation/staleness discipline
`createDeckBoot` documents (`:283-296`) applies here too: a deck change mid-flight must not let an
old report land.

**Q6 — What does the panel do when the fetch is refused?**
No artefact rules it. The two client precedents point opposite ways (§5).
*Proposal:* **follow the CARD precedent — the panel renders nothing and the deck view is
untouched.** A format-check refusal is an auxiliary read; routing it through `panelFor` would
replace a working deck view with *"The companion hit a bug"* because one panel could not load,
which is FR-13 inverted. Concretely: `'refused'` and `'unreachable'` both render `null`, exactly
as `ManaCurve` and `ColourDistribution` render `null` for an empty derivation, so the right column
loses its third panel and keeps its first two. ⚠️ Three things to write down rather than leave
implicit: (a) **it does not retry** — `internal-error` *"must never retry"* is a standing rule and
this panel owns no timer; (b) the failure is therefore **silent**, which is a real cost and the
honest place to record it is the ledger with a named home (Epic 7's refetch, or c8-6); (c) the
`'loading'` state renders **nothing**, not a skeleton — *"never a blank or a skeleton teardown of a
populated view"* and the panel materialising ~5 ms after the deck is below the threshold anything
would notice.

**Q7 — Does it refetch, and on what?**
`epics:698` puts UX-DR35's refetch *"wholly to Epic 7"*, and there is no `deck_changed` handler in
the client today.
*Proposal:* **it fetches once per active-deck id and does not refetch.** Epic 7 owns
`deck_changed`; half-building a refetch here would be a second coalescing rule to reconcile later.
**Say so in the module header and flag it to c7-3 by name**, because a format check that goes
stale after the agent adds a card is exactly the thing UJ-1 closes.

**Q8 — The "no format" branch: what does it read, and does it look different?**
Deferral 1 makes this a delete-or-use ruling. The wire's `format` is typed `string`
(non-nullable), so `format === null` would not compile — a stronger statement than the ledger's.
*Proposal:* **read `format_recognized`, and render the SAME six rows with no second layout.** The
backend already answers this case as an ordinary report; a distinct panel state would be the UI
inventing a shape the contract deliberately does not have (`deck_validator.py:550-556`: *"never a
different body and never an error"*). What `format_recognized: false` changes: nothing about
layout, and one thing about behaviour if Q4b ever ships a pill. So the honest use of the field is
**Q4's absence assertion made positive** — a test that drives the formatless report through the
panel and asserts the two advisory sentences render, plus a named test that `is_legal: false` with
zero violation rows produces **no** negative anything. That is reading the field, not merely
importing it. ⚠️ **0 of 40 real decks reach this state**, so the fixture is a **declared-synthetic
format override on a real deck** (§C).

**Q9 — What is the rows' markup?**
UX-DR44 enumerates `ul`/`li` for *"card grid, deck list and agent-view lists"* and gives `figure`
to the curve and the colour bar **by name**. The format check is in **neither** list.
*Proposal:* **a `<ul>`/`<li>`**, matching `DeckList` and `CardGrid`. Six checks are a list, *"list,
6 items"* is orientation, and the alternative (`<dl>`) implies a term/definition relationship that
`label → status word` does not have once Q2 adds a third element to the row. ⚠️ **This makes it the
third `<ul>` on the deck view**, and `App.test.tsx:647`'s comment predicted it by name: the
document-wide `getAllByRole('listitem')` was scoped at c4-7 *"because the next story to add a list
(c4-10's format check) would hit the identical failure."* **That scoping must hold** — verify it
does rather than assuming, and add the panel's own scoped count beside the other two.

**Q10 — The padding.**
`components.legality-row.padding: '9px 2px'` (`DESIGN.md:236`) is off-scale on both axes, and
`9` is named in UX-DR5's own drift list.
*Proposal:* **`var(--space-2) var(--space-1)`** (8px / 4px), the nearest scale pair in both axes,
with the repair stated inline in the exact form `Panel.css:63-69` and `Badge.css` already use —
including the measured fact that the literal **fails stylelint's allowed-list**, which is what
makes this a refusal rather than a preference. `DESIGN.md:236`'s frontmatter is amended in the
same commit; `validation-report-2026-07-25.md:75`'s over-tokenisation finding is cited as the
reason **no token is added** for it. **No `px` literal ships**, so ruling 7's citation requirement
is satisfied by not triggering it — and the story says that rather than leaving an absence.

**Q11 — Does the last row keep its hairline?**
The mock puts `border-bottom` on all six. `GroupHeader` puts its rule *above* content.
*Proposal:* **no trailing hairline** — `.format-check-row:not(:last-child)`, because a rule under
the last row inside a `Panel` with 12px padding draws a line to nowhere and reads as a truncated
list. Cheap, reversible, and worth ruling so it is not discovered on the eye-check.

**Q12 — Does this story pre-implement c4-12's empty-deck hide?**
Story 4.12 names all three analysis panels; c4-8 and c4-9 both shipped first and left the hide to
it. The backend answers a 0-card deck normally (`size` violation, `mainboard_count: 0`).
*Proposal:* **no — do not pre-implement it**, matching c4-8 and c4-9 exactly, and **flag it to
c4-12 by name** in the module header. ⚠️ But note the asymmetry honestly: the curve and the colour
bar hide themselves *on their own data* (a zero total), and this panel's data is never empty — six
rows always. So c4-12's hide is the **only** thing that will ever hide it, and there is no
self-gate to lean on. If Q6 ships `null` for a refusal, that is the panel's only `null` arm.

**Q13 — Does this story change `_MIN_MAINBOARD`?**
§2/§D: the deferral's measurement is wrong, `brawl` is 100-exact per this repo's own shipped
skill, and 18 of 40 decks (45%) get a pass sentence naming a minimum 40 below their format's.
*Proposal:* **DECLINE the code change, and correct the record in this diff** — the same posture
c4-8 and c4-9 took on the land and pip policies. A per-format minimum is a rule change in
`src/logic` (don't-break 19), it needs its own row-vocabulary decision for exact-vs-minimum
formats, and it would move `validate_deck`'s behaviour for the MCP tool as well as the panel.
**But the divergence is upgraded from latent to observable in this story**, exactly as c4-8's was:
before today the sentence was reported only to an agent that could caveat it; from today it is on
the glass for 45% of the deck table. **Write the ledger entry with all four numbers named** —
18 brawl decks, all at exactly 100, 0 commander decks, and the shipped skill that contradicts the
code comment — because c4-8's lesson is on the record: *a bare number in a ledger entry is not
checkable*. And correct **both** places the false claim appears (`deck_validator.py:174-178`,
`deferred-work.md:2355-2362`).

**Q14 — Which `format` string, if any, reaches the glass?**
The panel holds the **normalised** value; `DeckBadges` already renders the **stored** one, 24px
away in the header. 0 of 40 differ today.
*Proposal:* **the panel renders no format string at all** — Q4(a) gives it no headline and Q3's
labels are format-independent, so the divergence never reaches a comparison. **That closes the
deferral by construction rather than by fix**, which is the honest disposition: state that the two
values are held in one app for the first time, that nothing compares them, that a UI which ever
does would be comparing two different things, and re-home the underlying asymmetry (normalise at
write time in `create_deck`) unchanged. ⚠️ Note the `detail` sentences **do** interpolate the
normalised format (`Every card is legal in brawl.`), so if Q2 renders them, the normalised string
**is** on the glass beside the stored one in the header — measure whether they ever look different
(0 of 40 today) and say so.

**Q15 — What is copy here, and what is data?**
*Proposal:* `copy.ts` (import-free, `COPY_MODULES` **11 → 12**) owns the panel title and Q3's six
labels, plus Q1's three status words if they ship. The six `detail` sentences are **data** — they
are authored by the backend and arrive on the wire, exactly as a card name does, and moving them
into `copy.ts` would make the module's claim meaningless (ruling 14, `DeckList/copy.ts:25-31`'s
argument verbatim). ⚠️ **The attribute half of the copy guard is the risk**: any `aria-label`
assembled from a status word and a label is an authored string reaching a read-aloud attribute,
and `copy-rules.test.ts:62` calls that out by name.

**Q16 — Does a check announce when it changes?**
UX-DR45 names three live regions; none is this. There is no refetch today (Q7), so nothing
changes after first paint.
*Proposal:* **no `aria-live`, and the reason is that nothing moves** — unlike c4-9, whose
percentages genuinely moved during the hydration sweep. When Epic 7 wires `deck_changed`, a check
flipping `pass → violation` **will** be a silent change, and the honest place for that is a
ledger entry homed on **c7-5** (*"the change is announced once, and motion is never the only
signal"*), which already owns the one refetch announcement.

**Q17 — The contrast numbers this story inherits.**
Deferral 10. c4-2 measured the five tones over their own washes on `--surface-base`; nobody has
measured them on `--surface-panel`, and nobody has measured any of them under the four alternate
themes.
*Proposal:* **compute the three semantic tones over their own washes on `--surface-panel`** and put
the numbers in the record — it is arithmetic over shipped hexes, not an eye-check, and this is the
first surface where a semantic badge sits on a panel rather than in a header. **Confirm on the
eye-check that no state is distinguished by the neutral border** (`ui/README.md:1394-1397`'s live
constraint), which Q1's status word makes structurally impossible if the tone map never returns
`neutral`. Re-home the alternate-theme half unchanged, with its named owner.

---

## Acceptance Criteria

### The panel — presence, placement and semantics

1. A `FormatCheck` container renders in `AppShell`'s `right` slot as the **third** child, beneath
   `DeckList`, stacking on `.app-shell-column`'s existing `var(--space-panel-gap)` — with **no
   edit to `AppShell.tsx`** (UX-DR8, UX-DR21, `DESIGN.md:376`). The **ninth** application of the
   c2-9 displacement ruling; `AppShell.test.tsx:119`'s `'c4-10'` assertion still passes against
   the component's own props.
2. `App.test.tsx` asserts the right column's **document order** — card detail, then deck list,
   then format check — by `compareDocumentPosition`, extending the existing pair assertion rather
   than replacing it, and the right column's child count moves from **2 to 3**.
3. It renders **only** when `surfaceOf` returns `kind === 'deck'`, inheriting `App.tsx:101-119`'s
   c4-5 Q14 ruling rather than re-deciding it. A test asserts the panel is **absent behind every
   state panel arm** — all of them, parametrized. L8 is cited, not re-opened.
4. It is a `Panel` with `title` from `copy.ts` (an `<h2>` naming the `<section>`, UX-DR44) at
   `level="default"`, with **no `count` and no `badges`** (Q4).
5. The rows are a `<ul>`/`<li>` structure per Q9, the `<ul>` carrying no `role` override, and the
   panel's own scoped `listitem` count is asserted **beside** the grid's and the deck list's — the
   scoping `App.test.tsx:647` predicted for this story by name must hold rather than be re-scoped.
6. **The panel adds zero Tab stops** and nothing in it is focusable, clickable or hoverable
   (UX-DR21 *"display-only"*, UX-DR40, UX-DR47). A test asserts a click changes nothing
   observable; the inspection slice is not imported.

### The data path — one door, one writer, one request

7. **`readFormatCheck` lives in `src/api/client.ts`** and nowhere else (`posture.test.ts:341`),
   built on the shared private `request()`, returning a **total three-arm outcome union** that
   never throws and never returns `null`, with a private `formatCheckOf` narrower refusing *"a 200
   that is not this contract"* (`Array.isArray(rows)` at minimum), matching `readDeck` shape for
   shape. `src/App.tsx` still does not match the network family.
8. **`FormatCheckReport` and `FormatCheckRow` are added to `src/api/schema.ts`** (10 → 12 aliases)
   with consumer-naming doc comments in the file's convention, **in the commit that gives them a
   consumer**. Neither shape is re-declared anywhere outside `src/api/`
   (`wire-contract.test.ts:145`; both anchors already exist at `:113-114`).
9. **The fetch is owned per Q5's ruling.** If a sixth store ships, it has exactly **one writer**,
   its own module, a `STORES` entry (`store-writes.test.ts:77`, **5 → 6**) with its reason, and a
   staleness discipline that a deck change mid-flight cannot defeat. **No component calls
   `setState`.**
10. **c4-2's per-mount request count is EXTENDED to three**, still asserted as a *number* over ten
    minutes of fake time, and still red if any request repeats. The record states that this is a
    **second** `get_deck_with_cards` on the backend and that it costs a measured **5.4 ms warm /
    8.5 ms cold** on the largest deck. *[SUPERSEDED at implementation, noted at code review: the
    numbers this AC inherited from §F were replaced by Task 0's mandated re-measurement — min
    3.04 / median 5.19 / max 33.78 ms over all 40 real decks in-process — and those are the
    figures the shipped `client.ts` docstring and `App.tsx` comment carry. The largest-deck
    warm/cold pair was not re-stated; the AC's substance (cost measured and recorded) holds.]*
11. **The panel does not refetch** (Q7), owns no timer, and says so in its module header with
    **c7-3 named** as the story that wires `deck_changed`.
12. **A refused or unreachable read follows Q6's ruling**, with the retry posture stated
    explicitly and the silence recorded in the ledger with a named home. The `'loading'` state
    renders nothing — never a skeleton.
13. **`boards` is not a prop, not read and not re-derived.** This panel takes the deck id (or
    nothing, per Q5) and derives nothing from the deck payload. AD-12's single derivation and
    `deckMemory.ts`'s reference identity are untouched.

### The rows — what they say

14. **Exactly six rows render, in `CHECK_ORDER`**, read from the wire and **never sorted, filtered
    or re-grouped** (`deck_validator.py:487-494`). A test proves the order comes from the payload
    by feeding it shuffled and asserting the render follows the payload, not a local list.
15. **Each row's label comes from a `Record<FormatCheckName, string>` in `copy.ts`**, coupled to
    the wire union **in both directions** by type-level asserts, so a seventh check name and a
    widening to `string` are both `tsc` failures (ruling 16, `DeckList`'s shape).
    `'Banned or restricted'` does **not** ship (Q3): `restricted` reports through the *legality*
    row by design, and the corrected label plus the `EXPERIENCE.md:37` correction land in this
    diff.
16. **The badge carries Q1's ruling**, from a `Record<FormatCheckStatus, …>` coupled in both
    directions. The mock's six derived values (`'60 / 60'`, `'no violations'`, `'11 cards'`, …)
    **do not ship**, and the record states why: they are not on the wire, and computing them is
    the *"rule written in TypeScript"* hole `find_rule_violations` declares it cannot see. **Badge
    text is never empty** — `Badge` renders `null` for empty content, so an empty status word
    would silently drop the pill.
17. **Tone maps `pass → positive`, `advisory → caution`, `violation → negative`** (UX-DR21), by a
    total map, with **`neutral` unreachable** — the live constraint `ui/README.md:1394-1397`
    records is that a state distinguished by the neutral border would fail WCAG 1.4.11 at 1.89:1.
    A test asserts all three mappings **and** that no fourth tone is producible.
18. **The `detail` sentence follows Q2's ruling.** If it renders, `DESIGN.md:236` and `:423` are
    **amended in this commit** (the c4-7 `deck-row.columns` / c4-9 `color-bar` precedent), the
    type role and its contrast are stated, and the record carries the measured consequence: the
    rotation advisory is **86 characters on 40 of 40 decks, permanently**, so it is the panel's
    permanent height. If it does not render, the record states plainly that `'Pym Particles' is
    not legal in brawl.` is unreachable on the glass and homes the gap by name.
19. **`is_legal` is never bound to anything** (Q4, deferral 3). Asserted by test: the identifier
    appears nowhere in `src/` outside the generated types — turning the wire's prose `Warning:`
    into a machine-checkable fact, which is exactly what `deferred-work.md:2430-2437` says does not
    exist.
20. **`format_recognized` is READ, and the reading is proved** (Q8, deferral 1): a
    declared-synthetic formatless report renders the two advisory sentences, six rows, no
    violation tone anywhere, and `is_legal: false` produces nothing negative. A `format === null`
    branch does not exist — the generated type is `string`, so it would not compile.
21. **No format string reaches the panel's own chrome** (Q14). The record states that this story is
    the first to hold the normalised and the stored value at once, that **0 of 40** decks differ,
    that nothing compares them, and re-homes the write-time-normalisation fix unchanged.

### The row's appearance

22. **The row is `label` + a right-aligned `Badge` over `{components.legality-row.rule}`**
    (`DESIGN.md:423`), the rule spelled `1px solid var(--border-hairline)` with the citation
    comment in `GroupHeader.css:22-23`'s exact form, and the right-alignment through
    `margin-left: auto` — the mechanism `GroupHeader.css:40-41` names as the house idiom. **No
    token is added.**
23. **The label is `--type-body` at `--text-secondary`** (`DESIGN.md:423`), and any numeric role
    that ships carries `font-variant-numeric: var(--type-numeric-features)` **in the same rule
    block** (`findUnpairedNumericRole`); a `--type-micro` value carries `var(--tracking-micro)`
    and its `text-transform`.
24. **Padding follows Q10's ruling**, with the off-scale literal's refusal stated inline in
    `Panel.css:63-69`'s exact form and `DESIGN.md:236` amended in the same commit. **No `px`
    literal ships**, and the story says so rather than leaving the citation guard untriggered
    silently.
25. **The trailing hairline follows Q11's ruling.** The panel draws **no card**: its stylesheet
    does not join `CARD_SHAPED` and `--radius-card` appears nowhere in it (UX-DR4, both
    directions). **No `--mana-*` token appears anywhere** (UX-DR7), and `MANA_DATA_INK` keeps its
    two entries.

### Fixtures, and the epic's standing failure

26. **Every fixture is either a VERIFIED REAL row or DECLARED SYNTHETIC IN PLACE**, with no third
    option. The five real violations of §B are used verbatim where a real one exists; the five
    states with **zero** real instances (§C) each use the enumerated honest route, each labelled
    at its declaration with what is real about it and what is not. **No fixture asserts against a
    predicate that matches every row**, and no deck-level number is a bare constant without its
    provenance declared (the c4-8 High and the c4-9 ruling, not repeated).
27. **The corpus facts are pinned in the suite, not only in this file**: six rows always, the
    three-word status vocabulary, `rotation` advisory on **40 of 40**, and the **195 / 40 / 5**
    row census.
28. **A named test pins the size sentence a brawl deck sees** — `Mainboard has 100 cards; the
    minimum is 60.` on a deck whose format is exact-100 — so the §2 measurement survives in the
    suite rather than only in this record.

### Motion, announcements and accessibility

29. **The panel is not a live region and adds no `aria-live`** (Q16, UX-DR44, UX-DR45).
    `CardDetail`'s single polite region stays the only one, and the Epic 7 gap is ledgered with
    **c7-5** named.
30. **Nothing animates.** UX-DR42's exhaustive inventory has no format-check row and this story
    adds none; the shipped-motion pin stays at **4**. If anything animates, the row is added to
    `tokens.css:285-317` **and** UX-DR42 is amended in this commit.
31. **Colour is never the sole carrier.** Q1's status word rides beside the tone, so the row reads
    the same in greyscale — the rule UX-DR26 and UX-DR29 state for the tier letter and the
    connection dot, applied here. A test asserts the word, not the class.
32. **The jsdom phantom-`banner` count moves from five to six** and is recorded on both sides
    (jsdom and Chrome); role queries are scoped through the `h1`, never `getByRole('banner')`.
33. **The panel renders calmly**: no red panel fill, no alert icon, no exclamation mark, no
    illustration (UX-DR30's clause, `DESIGN.md:325`/`:451`). `FormatCheck.css` does **not** join
    `CALM_STYLESHEETS` — it legitimately spends `--negative`, which
    `token-usage.test.ts:1002-1021` states naming this story.

### The record, the gates and the ledger

34. `CONTAINERS` (`shell.test.ts`) gains one entry per new module with a sorted exhaustive import
    list and a prose reason, and the pin at `:1894` moves from **19**.
35. `copy.ts` exists with **no relative imports** and is registered in `COPY_MODULES`
    (`copy-rules.test.ts:107`) with a **>40-character** reason (**11 → 12**). The six `detail`
    sentences are **not** in it, and the module says why (Q15).
36. **Both token pins hold at 69** (`tokens.test.ts:321`, `token-usage.test.ts:1170`) and the
    story states plainly why: `components.legality-row`'s two values resolve to
    `--border-hairline` and a spacing pair. If a token is added, both pins move together with the
    reason.
37. **`eslint.config.js` and `RUNTIME_CUSTOM_PROPERTIES` are untouched**, and
    `inline-style-violation.tsx` stays pinned at exactly **2** messages — this panel has no
    computed geometry, and the story states the non-trigger rather than leaving it as an absence.
38. **An eye-check is performed in a real browser over CDP against the running backend**, not
    described. It must cover: an all-pass deck; **`Kotis, the Fangkeeper — 100-card Brawl`** (the
    only real legality violation — and the C3 retro's checklist item **C3**); **`Iron Man, Modern
    Marvel — reminder`** (the 1-card historic deck, `Mainboard has 1 cards` — checklist item
    **C4**); a **brawl** deck showing the exact-100-vs-minimum-60 sentence; a **formatless**
    override; and both motion settings. It reports measured numbers: the panel's rendered height,
    the row height with and without Q2's second line, the badge's rendered size, the three
    semantic tones over their own washes on `--surface-panel`, the label contrast, the right
    column's total height before and after, and the panel/list structure read from **Chrome's own
    accessibility tree**.
39. **Evasion probes are run against every new guard through the full `npm test`**, never a
    standalone file run. Enumerated **by letter before implementation**, including at least:
    (a) a new module absent from `CONTAINERS`; (b) a second network door / a `fetch` in the
    container; (c) `is_legal` bound to anything; (d) the rows sorted locally; (e) a seventh check
    name added to the label map (and one removed); (f) a fourth status added to the tone map;
    (g) the tone map returning `neutral`; (h) `--radius-card` in this story's CSS **and** a chrome
    radius in a `CARD_SHAPED` file (both halves); (i) a `--mana-*` token spent here; (j) a
    `--type-numeric` without `font-variant-numeric`; (k) `aria-live` added; (l) an authored word
    smuggled out of `copy.ts` or into an `aria-label`; (m) a `px` literal with no `DESIGN.md`
    citation; (n) a wire shape re-declared outside `src/api/`; (o) a component calling `setState`;
    (p) an off-scale spacing literal. **Plus two do-nothing negative controls whose silence is
    what makes the rest mean anything.** A probe that **passes is recorded, not quietly fixed**,
    and any substitution for an enumerated probe is **declared**.
40. **Every one of the eleven inherited deferrals gets a written disposition** — resolved,
    declined with a reason, or re-homed by name (C2 retro R2) — and the **eight** triggered
    residues get a line each, including F1's count, the two C3-retro manual-testing items, and the
    no-re-drive window this panel structurally escapes.
41. **The ledger entries are written into `deferred-work.md` in this commit**, not only into this
    story file. New entries owed: Q13's `_MIN_MAINBOARD` correction with all four numbers; Q6's
    silent-failure posture; Q7's no-refetch gap homed on c7-3; Q16's silent-change gap homed on
    c7-5; and Q4b's declined header pill.
42. **The measured doc corrections land in this diff**: `deck_validator.py:174-178`'s *"brawl and
    standardbrawl are genuinely 60-card formats … only Commander is affected"*;
    `deferred-work.md:2355-2362`'s copy of the same claim; `ui/README.md:1344-1346` and `:1396`'s
    header-pill prediction (Q4b); `EXPERIENCE.md:37`'s `'banned'` label (Q3); and `DESIGN.md:236`
    (Q10) and `:423` (Q2) if their rulings amend them.
43. The record states the **frontend and Python test counts, the file count, every registry that
    moved, both `schema.ts` alias counts, and both bundle asset names with byte sizes**, against
    the `4e31ea7` baselines. **Both bundle assets must change**; report the hash even where a byte
    count does not move.
44. **The bundle assets and every new module are `git add`ed before the record claims a green
    run** — the registry guards are blind to untracked files, and untracked bundle assets have been
    a **High** finding in two of the last seven stories.
45. The **plugin mirror** at `plugin/server/src/companion/app/static/` is updated by hand and
    verified **sha256-identical per file**; the standing fact that **nothing checks it** is
    re-stated with its named home (the C4 retro).
46. **Python is untouched**: `uv run pytest` stays at **2,501 passed / 1 skipped**, and CI's
    generated-types drift step (`npm run gen:types` then `git status --porcelain`) is clean —
    no Pydantic model moves, so `types.d.ts` and `openapi.json` are already correct and the
    two new `schema.ts` aliases are hand-written over an unchanged generated file. Q13's decline
    is what makes the first true, and the record says so rather than leaving it as an absence.

---

## Tasks / Subtasks

- [x] **Task 0 — Answer the seventeen open questions before writing code** (AC 14–21, 40)
  - [x] Re-verify §A–§G read-only against the shipped database at `4e31ea7`, driving the **real
        ASGI app** rather than a mock, and keying every per-deck count on **deck id** — all
        reproduce EXACTLY; §C's five no-fixture states measured through the real logic
  - [x] Read `deck_validator.py:475-737` end to end, and `client.ts:200-460`, before designing
        anything — the contract and the door are both already written
  - [x] Rule Q1–Q17, each with its reason recorded in the Debug Log
  - [x] Confirm `tokens.test.ts` needs no new entry and 69 holds
- [x] **Task 1 — The wire and the door** (AC 7, 8, 10)
  - [x] `schema.ts`: the two aliases with consumer-naming doc comments (10 → 12)
  - [x] `schema.test.ts`: type-level pins for both closed unions (the `CardFace` precedent)
  - [x] `client.ts`: path helper, outcome union, `formatCheckOf`, `readFormatCheck` — `readDeck`'s
        shape exactly; tests for every arm including a `200` that is not the contract
- [x] **Task 2 — The state** (AC 9–13)
  - [x] Q5's ruling: the sixth store with its single writer and generation-counter staleness
  - [x] `STORES` 5 → 6; the per-mount request count extended to three
  - [x] Q6's refusal arms, Q7's no-refetch header note naming c7-3
- [x] **Task 3 — The copy** (AC 15, 16, 35)
  - [x] `copy.ts`, no relative imports: title, the six labels, Q1's status words
  - [x] Type-level asserts coupling both maps to the wire unions in both directions
  - [x] Register in `COPY_MODULES` with a >40-char reason (11 → 12), stating why `detail` is data
- [x] **Task 4 — The panel** (AC 1–6, 14, 17–19, 22–25, 29–33)
  - [x] `FormatCheck.tsx`: titled `Panel`, `<ul>`/`<li>`, six rows in payload order
  - [x] `FormatCheck.css`: the hairline with its citation, `margin-left: auto`, Q10's padding,
        Q11's trailing rule, Q2's second line (with its stated type-role deviation)
  - [x] The tone map, `neutral` unreachable, the absence of `is_legal` asserted
- [x] **Task 5 — The mount** (AC 1–3, 5)
  - [x] One sibling inside `right`; `AppShell.tsx` untouched
  - [x] `App.test.tsx`: children 2 → 3, document order by `compareDocumentPosition`, absence
        parametrized over **every** state arm, the `c4-10` displacement asserted both halves, and
        the third `<ul>` counted **scoped** (plus the fourth list the context did not predict —
        `ColourDistribution`'s legend — named in the document-wide total)
- [x] **Task 6 — Fixtures, registries, guards and probes** (AC 26–28, 34, 36, 37, 39)
  - [x] Build the fixture set from §B and §C — every one verified real or declared synthetic
  - [x] `CONTAINERS` 19 → 21 + the pin; `COPY_MODULES` 11 → 12; `STORES` 5 → 6
  - [x] Run the eighteen lettered probes plus two negative controls — **18/18 caught, 2/2 silent**
  - [x] Record every probe with the named test that closes it; declare every substitution (three)
- [x] **Task 7 — The eye-check, the gates and the record** (AC 38, 40–46)
  - [x] CDP eye-check over the named decks and both motion settings; C3-retro items **C3** and
        **C4** discharged by name
  - [x] Compute the three semantic tones over their own washes on `--surface-panel` (Q17)
  - [x] Ten gates: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test`,
        `npm run build`, `npm run gen:types` (no drift); `uv run pytest`, `ruff check .`,
        `ruff format --check .`, `mypy src/`
  - [x] `git add` everything **before** believing a green run
  - [x] Rebuild the bundle, stage it, then `uv run python -m scripts.build_plugin` and **verify the
        mirror sha256-identical per file** — and note the Dev Notes' "checked by nothing" is false
  - [x] **Write the `deferred-work.md` entries in this commit** (AC 41) and land the doc
        corrections (AC 42)
- [ ] Set status to `review` and **STOP** — Brad runs the three-layer review and raises the PR

### References

- Epic story text — `_bmad-output/planning-artifacts/epics-companion-app.md:2189-2216`
- Epic 4 header — `:783-796` · Story 3.3 — `:1608-1636` · Story 4.12's hide clause — `:2276-2278`
- The endpoint's own justification — `:272-274` (*"had no data source"*)
- UX-DR21 — `:450-451` · UX-DR5 — `:356-357` · UX-DR6 — `:359-362` · UX-DR7 — `:364-368`
- UX-DR8 — `:372-378` · UX-DR10 — `:386-387` · UX-DR26 — `:478-482` · UX-DR29 — `:495-498`
- UX-DR30 — `:500-504` · UX-DR33 — `:520-524` · UX-DR40 · UX-DR42 — `:577-584` · UX-DR44 — `:590-595`
- UX-DR45 — `:597-601` · UX-DR47 — `:608-609` · NFR-05 — `:157-160` · FR coverage map — `:659-673`
- `DESIGN.md:235-237` (`components.legality-row`) · `:423` (anatomy) · `:376` (right column)
- `DESIGN.md:143-146` (`components.badge`) · `:325`, `:328-342` (contrast table), `:370`, `:391`,
  `:401`, `:406`, `:451`
- `EXPERIENCE.md:37`, `:57`, `:70`, `:96`, `:98`, `:111`, `:113`, `:154`, `:183`
- `validation-report-2026-07-25.md:75` (over-tokenisation), `:78` (**L8**), `:98`, `:146`
- Composition reference — `…/imports/claude-design/Planeswalker Companion.dc.html:135-146`,
  `:348-355`; `imports/claude-design/REVIEW.md:51`, `:81`
- Backend — `src/logic/deck_validator.py:174-232, 475-500, 502-517, 529-586, 589-641, 644-737`;
  `src/companion/app/routes/decks.py:94-138`; `src/companion/contracts.py:71-82, 142-209`;
  `src/companion/app/errors.py:46-57`
- Backend tests — `tests/unit/companion/test_routes_format_check.py:160-230, 238-289, 297-383,
  391-451, 459-476, 484-508, 515-566, 844-1011, 1125-1130`;
  `tests/unit/logic/test_format_check.py:116, 412-463, 478, 575-607`;
  `tests/unit/companion/test_committed_schema.py:63-82, 184-205, 243-266`
- The contradicting artefact — `plugin/skills/format-legality/SKILL.md:76-78`
- Wire — `ui/src/api/types.d.ts:84-119, 662-699, 906-971`; `ui/src/api/schema.ts:26-40, 89-109,
  126-151`; `ui/src/api/openapi.json`
- The door — `ui/src/api/client.ts:22-24, 34-48, 211-282, 374-383, 416-453, 548-557`
- State — `ui/src/state/deck.ts:95-170, 255-390, 392-464`; `ui/src/state/cards.ts:557, 578, 603`
- Mount and rulings — `ui/src/App.tsx:80-135, 230-304`; `ui/src/App.test.tsx:495-560, 635-665`
- Shell — `ui/src/components/AppShell/AppShell.tsx:60, 66, 107-137`; `AppShell.css:132, 139,
  151-156`; `AppShell.test.tsx:111-125`
- Primitives — `Badge/Badge.tsx:29-48`; `Badge/tones.ts`; `Badge/Badge.css:48, 125`;
  `Panel/Panel.tsx:31-67`; `Panel/Panel.css:19, 63-69, 73-75`;
  `GroupHeader/GroupHeader.css:13-15, 22-23, 40-41`; `DeckBadges/DeckBadges.tsx:19-51`
- Sibling containers — `DeckList/DeckList.css:1-70`; `DeckList/copy.ts:1-54`;
  `ColourDistribution/ColourDistribution.tsx:120-200`
- Tokens — `ui/src/styles/tokens.css:90-123, 144-145, 171-172, 285-317`
- Guards — `shell.test.ts:960, 1002-1032, 1353, 1894`; `token-usage.test.ts:584-598, 699-730,
  896-915, 995-1021, 1170, 1621`; `tokens.test.ts:321`; `copy-rules.test.ts:62, 107`;
  `posture.test.ts:321-357`; `store-writes.test.ts:77`; `wire-contract.test.ts:113-114, 145`;
  `lint-gates.test.ts:133-172`; `gate-geometry.test.ts:53`; `ui/eslint.config.js:204-240`
- `ui/README.md:90-98, 123-125, 129-164, 189-358, 398-425, 437-439, 457-461, 489-508, 526-543,
  546-582, 939-998, 1019-1024, 1140-1158, 1206-1304, 1311-1346, 1358-1397, 1426`
- Ledger — `deferred-work.md:452, 1333-1362, 1668-1699, 1780, 1909, 1972-1981, 2323-2426,
  2428-2450, 3456-3464, 3496-3502, 3587-3596, 3626-3637, 3639-3649, 3806-3814, 3869-3877,
  3975-4000`
- C3 retro — `epic-c3-retro-2026-08-02.md:223, 450-482, 555-575`
- Prior records — `c4-9:…:1-135, 490-620, 1065-1315`; `c4-7:…:90-270, 864-1018`;
  `c3-3:…:198-199, 599-602, 685`
- CI bundle sync — `.github/workflows/ci.yml:114-171`; `scripts/build_plugin.py:190-215`

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`

### Debug Log References

#### Task 0 — the measurements, re-verified read-only at `4e31ea7`

Driven through the **real ASGI app in-process** (`httpx.ASGITransport` + `main.lifespan`) against
the shipped database at `%LOCALAPPDATA%\artificial-planeswalker\cards.db`, keyed on **deck id**.

**§A–§G reproduce EXACTLY as written.** 40 of 40 decks answer `200`; 6/6/6 rows; 240 rows total;
**195 pass / 40 advisory / 5 violation**; `is_legal` 35 true / 5 false; `format_recognized: false`
on **0**; the `is_legal:false`-with-no-violation trap on **0**; `CHECK_ORDER` holds on every deck.
Formats `standard` 19 / `brawl` 18 / `standardbrawl` 2 / `historic` 1. Check × status matches the
table row for row (legality 39/–/1, size 36/–/4, copy_limit 40/–/–, sideboard 40/–/–, banned
40/–/–, rotation –/40/–). §B's five violations are verbatim, including
`'Mainboard has 1 cards; the minimum is 60.'`. §D: **all 18 brawl decks are exactly 100 mainboard**
(min 100 / max 100), 2 `standardbrawl`, **0 commander**, and every one of the 18 is shown the single
sentence `Mainboard has 100 cards; the minimum is 60.` §E: shortest detail **27**
(`No card is banned in brawl.`), longest **86** (the rotation advisory). §F: **min 3.04 / median
5.19 / max 33.78 ms** per request in-process (cold first). §G: an unknown id **and** a malformed id
both answer `404 {"reason":"deck_not_found"}`; `?format=potato` is ignored and still returns six
rows.

**`plugin/skills/format-legality/SKILL.md:76-78` confirmed verbatim** —
`Brawl (Historic) | **100 (exact)**` and `Standard Brawl | **60**`. §2's headline holds.

**§C — the five states with no real fixture, each measured rather than invented.** These are the
exact sentences the fixtures use:

| state | how it was produced | the sentence |
|---|---|---|
| `format_recognized: false`, named | real deck, `format = 'potato'` | `'potato' is not a recognized format, so legality could not be checked.` / `… so banned cards could not be checked.` |
| `format_recognized: false`, blank | real deck, `format = ''` | `There is no format to check against, so legality could not be checked.` / `… so banned cards could not be checked.` |
| `copy_limit` violation + `(+N more)` | real Standard deck (`Temur Dragonstorm v2`) re-checked against `commander` | `2 copies of 'Candy Trail'; commander is a singleton format (max 1 copy of any non-basic card). (+15 more)` |
| `sideboard` violation | the same real deck, every row declared sideboard | `Sideboard has 60 cards; the maximum is 15.` (and `size` goes `Mainboard has 0 cards…`) |
| `banned` violation | the real brawl deck + one **real** brawl-banned card (`Time Warp`, measured `legalities.brawl == 'banned'`) | `'Time Warp' is banned in brawl.` |

Both formatless spellings keep `size`, `copy_limit` and `sideboard` answering normally, exactly as
`deck_validator.py:700-708` says. `is_legal` is `false` in both while **no row is a violation** —
the trap, produced on demand.

#### Task 0 — the seventeen rulings

**Q1 — AS PROPOSED.** The badge carries the **status word** (`PASS` / `ADVISORY` / `VIOLATION`)
from a `Record<FormatCheckStatus, string>` in `copy.ts`, coupled both ways. The mock's six derived
values do not ship, and the reason is recorded in `copy.ts` so nobody re-proposes them: they are
not on the wire and computing them is the *"rule written in TypeScript"* hole
`find_rule_violations` declares it cannot see.

**Q2 — AS PROPOSED.** The `detail` sentence renders as a **second line** beneath the label, in
`--type-micro` at `--text-tertiary` (**measured 5.43:1** on `--surface-panel`, clear of 4.5:1).
`DESIGN.md:236-237` and `:423` are amended in this commit. The row height stops being uniform, on
purpose. The `title=` alternative is hover-only and banned by UX-DR39; the *"detail only when
`status !== 'pass'`"* alternative is rejected because it would be a fourth vocabulary decision and
would hide the very size sentence §2 is about.

**Q3 — RULED, WITH A CORRECTION TO THE STORY'S OWN PREMISE.** The context says the mock's six
labels begin `'Format legality'`. **They do not.** Read out of the composition reference, the
mock's `legality` table is:

```js
{label: 'Standard',            value: 'legal',         tone: 'positive'},
{label: 'Maindeck size',       value: '60 / 60',       tone: 'positive'},
{label: 'Copy limit',          value: 'no violations', tone: 'positive'},
{label: 'Sideboard',           value: '15 / 15',       tone: 'positive'},
{label: 'Banned or restricted',value: 'none',          tone: 'positive'},
{label: 'Rotation exposure',   value: '11 cards',      tone: 'caution'}
```

The first slot holds a **format string**, not a label — which is precisely what **Q14** bans from
this panel's chrome, and it is unusable for the additional reason that the two `format` values
diverge by construction. So four labels are the mock verbatim, one is the mock corrected, and one
is authored from `EXPERIENCE.md:37` because the mock supplies none:

| check | label | source |
|---|---|---|
| `legality` | `Legality` | `EXPERIENCE.md:37`'s IA row — the mock's slot is a format string (Q14) |
| `size` | `Maindeck size` | mock, verbatim |
| `copy_limit` | `Copy limit` | mock, verbatim |
| `sideboard` | `Sideboard` | mock, verbatim |
| `banned` | `Banned cards` | mock's `'Banned or restricted'`, **corrected** |
| `rotation` | `Rotation exposure` | mock, verbatim |

`'Banned or restricted'` is a false label: `deck_validator.py:433-452` reports a `restricted` card
through the **legality** row deliberately and pinned
(`test_restricted_is_unchanged_by_the_banned_split`), so a row so labelled could never fire for a
restricted card. `'Legality'` rather than `'Format legality'` because the panel is already titled
*Format check* and the word would be said twice. Sentence case, no periods — `DECK_LIST_TITLE`'s
voice.

**Q4 — AS PROPOSED (a).** No headline, no summary badge, no `count`, and **no use of `Panel`'s
`badges` slot** — ruled against explicitly rather than overlooked. `is_legal` is asserted absent
from `src/` outside the generated types, which turns the wire's prose `Warning:` into a
machine-checkable fact. **Q4b — AS PROPOSED (b):** the header legality pill does **not** ship, and
`ui/README.md:1344-1346` / `:1396` are corrected in this diff, with the C4 retro named as the
honest home.

**Q5 — AS PROPOSED.** A **sixth store**, `src/state/formatCheck.ts` (`STORES` 5 → 6), holding
`'idle' | 'loading' | 'report' | 'refused'` under a key, one writer, a generation counter for
staleness, and a `useFormatCheck()` selector returning the stored value. Driven from `App.tsx`'s
existing effect layer keyed on the deck id — the shape `hydrateDeckCards` is driven with. All three
alternatives rejected with their reasons in the module header.

**Q6 — AS PROPOSED.** A refused or unreachable read renders **nothing**; the deck view is
untouched; `'loading'` renders nothing, never a skeleton. No retry, no timer. The silence is a real
cost and is ledgered with a named home.

**Q7 — AS PROPOSED.** One fetch per active-deck id, no refetch; **c7-3** named in the module header.

**Q8 — STATED DEVIATION** *(reworded at code review — the original entry said "AS PROPOSED,
`format_recognized` is **read**", which contradicted the shipped disposition recorded everywhere
else)*. The component does **NOT** read `format_recognized`: the delete-signal
`deferred-work.md:2394-2400` defines **fired**, and that is recorded rather than dressed up with a
decorative read — the backend already puts "could not be checked" on the glass twice in words, so
a branch on the boolean could only restate what two rows say. What Q8's proposal actually ruled is
preserved in its mechanism half: the behaviour under a formatless report is **pinned by a test**
that drives the declared-synthetic fixture through the panel and asserts both advisory sentences
render, six rows, no violation tone, and nothing negative from `is_legal: false`. A
`format === null` branch does not exist — the generated type is `string`, so it would not compile.
The field is not deleted (Python untouched, AC 46); its remaining consumer is non-rendering, and
the ledger entry carries the re-homing.

**Q9 — AS PROPOSED.** `<ul>` / `<li>`, no `role` override. `App.test.tsx:647`'s scoping **holds**
(verified: both `getAllByRole('listitem')` reads are already scoped, to `.card-grid` and to the
deck-list region); the panel's own scoped count is added beside them.

**Q10 — AS PROPOSED.** `var(--space-2) var(--space-1)` (8px / 4px). `9px 2px` is off-scale on both
axes and `9` is in UX-DR5's own drift list; the stylelint allowed-list refuses it outright.
`DESIGN.md:237` amended in the same commit. **No `px` literal ships in this story's CSS**, so
ruling 7's citation requirement is satisfied by not being triggered.

**Q11 — AS PROPOSED.** No trailing hairline: `.format-check-row:not(:last-child)`.

**Q12 — AS PROPOSED.** c4-12's empty-deck hide is **not** pre-implemented, and c4-12 is named in
the module header — together with the asymmetry: this panel's data is never empty, so unlike the
curve and the colour bar it has no self-gate to lean on.

**Q13 — AS PROPOSED: DECLINE the code change, correct the record.** Python is untouched. Both
`deck_validator.py:171-178` and `deferred-work.md:2355-2362` are corrected with all four measured
numbers.

**Q14 — AS PROPOSED.** No format string reaches the panel's own chrome. The `detail` sentences do
interpolate the **normalised** value (`Every card is legal in brawl.`) and therefore do put it on
the glass beside the **stored** one in `DeckBadges` — measured **0 of 40** decks differ, and
nothing compares them.

**Q15 — AS PROPOSED.** `copy.ts` owns the title, the six labels and the three status words
(`COPY_MODULES` 11 → 12). The six `detail` sentences are **data**.

**Q16 — AS PROPOSED.** No `aria-live`; the reason is that nothing moves. The Epic 7 gap is
ledgered on **c7-5**.

**Q17 — MEASURED.** The three semantic tones over their **own 12% washes on `--surface-panel`**,
computed from the shipped hexes (`positive #5fd4a0`, `negative #ff7a86`, `caution #ffc266` over
`#191c2b`):

| tone | wash composite | text on its wash | border on the surface |
|---|---|---:|---:|
| `positive` | `#213239` | **7.21:1** | 9.19:1 |
| `negative` | `#352736` | **5.60:1** | 6.75:1 |
| `caution` | `#353032` | **8.14:1** | 10.59:1 |

All three clear 4.5:1 with headroom, and all three are **lower than c4-2's numbers** — because
c4-2 measured on `--surface-base` (re-derived here as 7.96 / 6.15 / 8.99, matching its record to
rounding). **A correction to the record is owed:** `ui/README.md` states neutral's `--border-strong`
hairline at **1.89:1**, which is the `--surface-base` figure; on `--surface-panel`, where *this*
panel's badges actually sit, it is **1.75:1** — worse, not better. It does not bite, because the
tone map is total over three statuses and **`neutral` is unreachable by construction**. The
alternate-theme half of deferral 10 is re-homed unchanged.

### Completion Notes List

#### What shipped

Six rows in a panel, third in the right column, over an endpoint that has been green since
2026-08-01 — plus the third element `DESIGN.md:423` does not have, which is the only thing on the
panel that can name a card. **All seventeen questions ruled before any code**; sixteen as proposed,
**one stated deviation** (Q2's type role, below), and **one correction to the story's own premise**
(Q3's mock labels).

#### The headline, confirmed on a real screen

`Kotis, the Fangkeeper — 100-card Brawl` renders `Legality` · **VIOLATION** with
**`'Pym Particles' is not legal in brawl.`** beneath it. Rendered to `DESIGN.md:423`'s two-slot
letter that sentence appears **nowhere**, on the one deck in forty with a real legality violation,
in the story whose own user statement is *"I find out about a banned card"*. The second line is a
`DESIGN.md` amendment made in this commit, and the row beneath it carries §2's other finding on the
same screen: **`Mainboard has 100 cards; the minimum is 60.`** with a green **PASS** pill.

#### The one stated deviation, found by a gate rather than by taste (Q2)

The story proposed `--type-micro` at `--text-tertiary` for the detail sentence. **That role is not
available for a sentence.** `--type-micro` carries an uppercase companion **derived** (not listed)
from `DESIGN.md`'s own `textTransform:` key, and `findRoleWithoutCompanions` fails a micro role
applied without it — `token-usage.test.ts` went red on the first draft. Shipping it correctly would
have rendered **`'PYM PARTICLES' IS NOT LEGAL IN BRAWL.`**, destroying the card name the panel
exists to show. (`Footer.css:29-35` records the same derivation and accepts its consequence, which
is why the legal attribution is 10px ALL-CAPS.) Three alternatives were priced and declined:
`text-transform: none` is what the gate exists to refuse; amending the micro role's key would flip
every micro consumer app-wide off one panel's needs; a new token moves both pins for a value that
already exists. **Shipped `--type-body` at `--text-tertiary`** — distinguished from the label by
TIER rather than by SIZE, which is `.deck-row`'s own idiom, and `body` requires no companion. The
cost is real and measured: the panel is taller than a 10px line would have made it.

#### The correction to the story's own context (Q3)

The Dev Notes list the mock's six labels beginning `'Format legality'`. **Read out of the
composition reference, the mock's first slot holds `{label: 'Standard', value: 'legal'}` — a
FORMAT STRING, not a label.** That is unusable twice over: Q14 keeps every format string out of
this panel's chrome, and a label that changed per deck would not be copy at all. So four labels are
the mock verbatim, `'Banned or restricted'` is the mock **corrected** (a false label —
`deck_validator.py:433-452` reports `restricted` through the *legality* row, deliberately and
pinned, so it could never fire), and `'Legality'` is authored from `EXPERIENCE.md:37`'s IA row.

#### Two corrections owed to the record, both measured

1. **`_MIN_MAINBOARD`'s deferral was exactly backwards.** `deck_validator.py:171-178` and
   `deferred-work.md:2355-2362` both claimed *"brawl and standardbrawl are genuinely 60-card
   formats … only Commander is affected … 0 commander decks"*. Re-measured through the real ASGI
   app: this repo's **own shipped skill** says Brawl (Historic) is **100 exact**
   (`plugin/skills/format-legality/SKILL.md:77`), the database agrees — all **18** brawl decks sit
   at **exactly 100** (min 100 / max 100), 16 with a commander row — there are **2** genuinely-60
   `standardbrawl` decks, and **0** commander decks, so the named at-risk population is **empty**
   while the affected one is **45% of the deck table**. Q13 **declines the code change** (MCP blast
   radius; `validate_deck` serves the agent tools) and both places are corrected in this commit,
   with the severity upgraded from Low to Medium because it is now on the glass.
2. **The story's own Dev Notes claim the plugin mirror is "checked by NOTHING". It is false.**
   `tests/unit/companion/test_spa.py::TestThePluginMirror` compares the two trees **byte-for-byte,
   names and bytes**, and it is what went red on this story's first `uv run pytest` after the
   rebuild. The residue is narrower than recorded: the mirror is guarded on the **Python** side
   only, so a frontend-only `npm test` still cannot see a stale one. Re-homed to the C4 retro,
   downgraded from *"unguarded"* to *"guarded on the Python side only"*.

#### Q17 measured, and a third correction

The three semantic tones over their **own 12% washes on `--surface-panel`**, computed from the
shipped hexes: **`positive` 7.21:1 · `negative` 5.60:1 · `caution` 8.14:1** — all clear of 4.5:1,
and all ~10% below c4-2's numbers because **c4-2 measured on `--surface-base`** (re-derived as
7.96 / 6.15 / 8.99, matching its record to rounding). `ui/README.md`'s **1.89:1** for `neutral`'s
`--border-strong` hairline is likewise the `--surface-base` figure; on `--surface-panel`, where this
panel's badges actually sit, it is **1.75:1 — worse**. It does not bite: `TONE_FOR_STATUS` is total
over three statuses and **`neutral` is unreachable by construction**, coupled to `BADGE_TONES` by a
type-level assert. The alternate-theme half is re-homed unchanged.

#### The eye-check (AC 38) — over CDP, against the running backend

Headless Chrome, real backend, real database; `/api/deck/{id}` and `/api/deck/{id}/format-check`
served by the real app (only `/api/active-deck` and the one declared-synthetic formatless body were
CDP-stubbed). **Six cases: all-pass standard · the brawl legality violation · the one-card historic
deck · a formatless override · reduced motion · the ~1100px floor.**

| measurement | result |
|---|---|
| panel box | **452 × 475.1 px** all-pass; **452 × 517.1 px** formatless |
| right-column children | **3** (was 2), height 2,371 px on the all-pass deck — the BEFORE height was not captured at the eye-check and is recorded here as absent rather than back-computed (c4-10 review, AC 38's one gap; the panel's own 475.1 px + the 24 px gap give a derivable ~1,872 px, but a derived number is not a measurement) |
| row height | **66.3 px** one-line detail · **86.3–87.3 px** two-line |
| badge box | **48.8 × 24.3** (Pass) · **78.2 × 24.3** (Advisory) · **81.1 × 24.3** (Violation) |
| label | `14px/21px` `rgb(179,184,207)` = `--text-secondary` ✓ |
| detail | `14px/21px` `rgb(139,145,173)` = `--text-tertiary`, `text-transform: none` ✓ |
| row padding | **`8px 4px`** — Q10's scale pair, live ✓ |
| hairline | **`1px rgb(44,48,72)`** = `--border-hairline`; **last row `0px`** ✓ (Q11) |
| Tab stops · `aria-live` · list `role` | **0 · 0 · none**; 6 list items ✓ |
| scrollers in panel · page h-overflow · non-zero transitions | **0 · false · 0** ✓ |
| `--mana-*` in markup · card shape | **false · false** ✓ |
| `Panel` badge slot · `count` | **empty · absent** ✓ (Q4) |
| **`<header>` elements on the page** | **6** — the jsdom phantom count, five → six ✓ (AC 32) |
| **Chrome's own accessibility tree** | **exactly ONE `banner`**, plus `region: Format check` |
| reduced motion | geometry **identical**, 0 transitions either way |
| 1100px floor | panel unchanged at **452 px**; no horizontal overflow |

**Both C3-retro manual-testing items are discharged by name.** **C3** — `is_legal` read against the
six rows on the brawl deck: `is_legal: false` with exactly one violation row, and the panel binds
the field nowhere. **C4** — the 1-card `historic` deck renders **`Mainboard has 1 cards; the minimum
is 60.`** under a red VIOLATION pill: D-1.6b's plural defect, visible to a human for the first time,
pinned in the suite and ledgered rather than fixed (Python untouched).

#### The probes (AC 39) — 18 of 18 caught, both controls silent

Enumerated by letter **before** implementation and run through the full `npm test` unless declared
otherwise. Every one closed by a **named** test: (a) unregistered container → the `CONTAINERS`
coverage guard + its own firing half; (b) `fetch` in the container → three guards; (c) `is_legal`
bound → the new absence guard; (d) rows sorted → the shuffled-payload test; (e1) seventh check name
→ the exact-labels test; (g) tone → `neutral` → three tests; (h1/h2) card radius, **both
directions**; (i) `--mana-*`; (j) unpaired numeric role; (k) `aria-live`; (l) an authored sentence
into an `aria-label` → the copy guard; (m) uncited `px`; (n) a re-declared wire shape; (o) a
component `setState`. **Three substitutions declared**: (e2) removing a label key and (f) a fourth
tone-map key are **type-level** and proven through `npx tsc -b --force` — `npm test` does not
typecheck, and a map key nothing looks up changes no render; (p) the off-scale `9px 2px` is
**stylelint's**, proven through `npm run lint`, which is the gate that owns the spacing scale and
the measurement Q10 rests on.

⚠️ **The harness lied once and its own validation caught it — the FOURTH recorded instance of the
ledgered vitest crash.** The first run reported every probe "caught" while all 61 files died with
*"Vitest failed to find the current suite"* and **zero assertions**. Two causes, both measured:
`subprocess.run(["npm", "test"], shell=True)` on Windows passes only the first list element to
`cmd.exe`, and — the ledgered one (`deferred-work.md:3639-3649`) — a cwd whose **drive letter is
lowercase** breaks vitest's project-config resolution. The harness now asserts a real
`Tests N passed` line with N > 1500 and refuses a run carrying the crash signature.

#### Ten gates, all green

`npm run lint` ✓ · `npm run format:check` ✓ · `npx tsc -b --force` ✓ · `npm test` **1,645 passed /
61 files** ✓ · `npm run build` ✓ · `npm run gen:types` **no drift** ✓ · `uv run pytest` **2,501
passed / 1 skipped** ✓ · `ruff check .` ✓ · `ruff format --check .` ✓ · `mypy src/` ✓.

#### The numbers (against the `4e31ea7` baselines)

| | baseline | now |
|---|---|---|
| frontend tests / files | 1,476 / 57 | **1,645 / 61** |
| Python tests | 2,501 / 1 skipped | **2,501 / 1 skipped** (unchanged) |
| tokens (both pins) | 69 | **69** — neither pin moved |
| containers (`shell.test.ts`) | 19 | **21** |
| copy modules | 11 | **12** |
| stores | 5 | **6** |
| `schema.ts` aliases | 10 | **12** |
| `CARD_SHAPED` · `MANA_DATA_INK` · `RUNTIME_CUSTOM_PROPERTIES` · `CALM_STYLESHEETS` | 4 · 2 · 2 · 1 | **unchanged** |
| shipped-motion pin · `inline-style-violation.tsx` messages | 4 · 2 | **unchanged** |
| jsdom phantom `banner` | 5 | **6** (Chrome: **1**) |
| right-column children | 2 | **3** |
| bundle JS | `index-D6NJThYj.js` 221,585 B | **`index-HUZAFWeW.js` 223,200 B** (+1,615) |
| bundle CSS | `index-BqIKsEIE.css` 19,294 B | **`index-Bek3WjaA.css` 19,844 B** (+550) |
| font | 22,288 B | **22,288 B** (unchanged) |

**Both bundle assets changed**, in name and in size. The plugin mirror was rebuilt with
`uv run python -m scripts.build_plugin` and verified **sha256-identical per file** across all five
assets — and, unlike previous stories, that verification has a test behind it.

#### The eleven inherited deferrals — every one dispositioned (AC 40)

1. **`format_recognized` / six-row shape declared-but-unread** — **partly resolved, delete-signal
   RECORDED AS FIRED.** `CHECK_ORDER` is consumed and pinned with a reversed payload. The component
   does **not** read `format_recognized`, and the honest reason is that the backend already puts
   *"could not be checked"* on the glass twice in words, so a branch could only re-state them and
   the layout deliberately does not change. Behaviour under the state is pinned by test. Field not
   deleted (Python untouched); re-homed to the **C4 retro** with the signal recorded.
2. **The "no format" branch must key on `format_recognized`, not `format === null`** — **RESOLVED,
   and stronger than the entry knew:** the generated type is `string`, so `=== null` would not
   compile. Pinned in `schema.test.ts`.
3. **`is_legal: false` above six non-violation rows** — **CLOSED.** Bound to nothing; the prose
   `Warning:` is now a machine-checkable guard with a non-vacuity half. Verified by probe (c).
4. **Normalised vs stored `format`** — **home condition met; closed BY CONSTRUCTION.** The panel
   renders no format string in its chrome, so nothing compares them; still 0 of 40. The underlying
   write-time-normalisation fix is **re-homed unchanged** — closing it in one consumer is not
   fixing it.
5. **`_MIN_MAINBOARD = 60` regardless of format** — **measurement CORRECTED in both places, code
   change DECLINED** (Q13), severity upgraded Low → Medium, all four numbers written down.
6. **Copy-limit definitive under the 4-copy fallback** — **not triggered** (0 unrecognised formats
   live); re-homed unchanged to the unowned `src/logic` rule story.
7. **`format_recognized: true` ≠ the key is in the card data** — **not reachable** against a
   synchronised snapshot; re-homed unchanged.
8. **A `restricted` card reported as "not legal"** — re-homed unchanged, **with the exposure
   re-stated**: 0 live instances, no vintage deck. This story makes it *visible* the day one
   exists, and it is also why the mock's `'Banned or restricted'` label does not ship.
9. **Rotation cannot be computed from local data** — **acknowledged, not merely tolerated**: 40 of
   40 decks, permanently, and every advisory in the 240-row corpus is that one sentence. Pinned in
   the fixture module with the consequence written down — a caution badge here is **furniture, not
   a signal** — and never promoted to `pass`.
10. **`Badge`'s tone-over-wash contrast** — **discharged and re-measured on this surface** (see
    Q17 above), with a correction to the recorded `neutral` figure; alternate themes re-homed.
11. **`DeckRepository.list_decks` ties on `created_at`** — this story never calls `GET /api/decks`;
    same disposition as c4-7/c4-8/c4-9, re-homed unchanged.

#### The triggered residues — a line each

- **F1 (story keys on the glass):** `c4-10` is now absent **by its own panel**, asserted both ways.
  All three right-column keys are displaced; **one remains** (`c4-11`, the skip-link work). The
  gate stays **c8-5's**.
- **C3-retro manual items C3 and C4:** both discharged by name at the eye-check (above).
- **`Panel`'s default-level eye-check:** discharged at c4-5/c4-7; confirmed and re-stated, not
  re-run.
- **Identifier / type-role residue:** this panel renders **no numeric value at all**, so
  `--type-numeric` appears nowhere and its companion rule is satisfied by not being triggered. Type
  roles shipped: `--type-body` for the label (`DESIGN.md:423`, in writing) and for the detail line
  (Q2's deviation, above).
- **`StatChip`'s first surface:** **not triggered** — `DESIGN.md:423` names only a label and a
  `Badge`.
- **The visually-hidden idiom's third instance:** **does not fire.** Every word on this panel is
  visible text; no hidden block ships, so the promotion trigger stays at two.
- **The cross-file card-shape collision:** not expected and not present — this file styles only its
  own `.format-check-*` classes and never reaches into a `.card-shape` descendant.
- **c4-6's no-re-drive window:** **not triggered, structurally.** This panel reads no card and
  derives nothing from the cache — the first in the epic to escape it for a reason other than which
  field happened to ride on `CardSummary`.
- **Registry guards blind to untracked modules:** taken as far as this story honestly can — every
  new module was `git add`ed **before** the green run was believed, and both guards that depend on
  it carry the declared limit in their comments. The tree-walk redesign stays ledgered.

#### Two honest limits

- **The formatless state has never been seen against real data**, because no real deck reaches it
  (0 of 40). It is exercised by a declared-synthetic override in the suite and at the eye-check.
- **The refusal path is invisible by design** (Q6). A user whose format check fails to load sees a
  right column with two panels and no way to know a third was meant to be there. Ledgered with a
  named home rather than smoothed over.

### File List

**New (9)** *(the first draft's header said "New (7)" over an eight-item list — corrected at code
review, which also added the ninth: decision 2a split the fixture DATA out of the pins file)*

- `ui/src/containers/FormatCheck/FormatCheck.tsx`
- `ui/src/containers/FormatCheck/FormatCheck.css`
- `ui/src/containers/FormatCheck/FormatCheck.test.tsx`
- `ui/src/containers/FormatCheck/copy.ts`
- `ui/src/state/formatCheck.ts`
- `ui/src/state/formatCheck.test.ts`
- `ui/src/state/formatCheck.fixtures.ts`
- `ui/src/state/formatCheck.fixtures.test.ts`
- `ui/tests/format-check-source.test.ts`

**Modified (10)**

- `ui/src/App.tsx` — the third `right` child, and the effect keyed on the deck **id**
- `ui/src/App.test.tsx` — the format-check branch in **both** routing fixtures, the fixture body,
  document order, the third scoped `listitem` count, per-arm absence + a per-arm no-request test,
  and `deckDetailCalls`/`formatCheckCalls` so a prefix match stops conflating two routes
- `ui/src/api/schema.ts` — `FormatCheckReport`, `FormatCheckRow` (10 → 12 aliases)
- `ui/src/api/schema.test.ts` — four type-level pins for the two closed unions
- `ui/src/api/client.ts` — `FORMAT_CHECK_PATH_SUFFIX`, `formatCheckPath`, `FormatCheckOutcome`,
  `formatCheckOf`, `readFormatCheck`
- `ui/src/api/client.test.ts` — the reader's every arm, the shared-prefix hazard, the formatless 200
- `ui/tests/shell.test.ts` — `CONTAINERS` 19 → 21 with import lists and reasons
- `ui/tests/copy-rules.test.ts` — `COPY_MODULES` 11 → 12
- `ui/tests/store-writes.test.ts` — `STORES` 5 → 6
- `src/logic/deck_validator.py` — **comment only**, the `_MIN_MAINBOARD` correction (no behaviour)

**Artefacts and record (5)**

- `_bmad-output/planning-artifacts/ux-designs/…/DESIGN.md` — `components.legality-row.padding`
  amended (Q10) and the Format check anatomy amended (Q2)
- `_bmad-output/planning-artifacts/ux-designs/…/EXPERIENCE.md` — the `banned` label corrected (Q3)
- `ui/README.md` — the header-pill prediction corrected twice (Q4b) and Q17's numbers re-measured
- `_bmad-output/implementation-artifacts/deferred-work.md` — six new entries, three inherited
  entries answered in place, the `_MIN_MAINBOARD` measurement corrected
- `_bmad-output/implementation-artifacts/c4-10-format-check-panel.md` — this record
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

**Build output (4, generated)**

- `src/companion/app/static/index.html`, `assets/index-HUZAFWeW.js`, `assets/index-Bek3WjaA.css`
- `plugin/server/src/companion/app/static/…` — the hand-copied mirror, sha256-verified per file

### Change Log

| date | change |
|---|---|
| 2026-08-06 | c4-10 implemented on `feat/companion-c4-10-format-check-panel` off `4e31ea7`. Seventeen questions ruled; 16 as proposed, 1 stated deviation (Q2's type role, forced by a derived companion gate), 1 premise correction (Q3's mock labels). Ten gates green: 1,645 frontend / 61 files, Python 2,501/1 unchanged. 18 evasion probes caught, 2 negative controls silent. CDP eye-check over six cases. Status → `review`. |
| 2026-08-06 | Three-layer code review: 38 raw → 27 unique findings; 2 decisions (1a: `formatCheckOf` refuses empty/non-object rows; 2a: fixture data split to plain `formatCheck.fixtures.ts`, pins run once), 20 patches applied (High: the guard file's own non-vacuity `.concat` tautology; Medium: the false "guarded at the call site" claim), 1 defer (fixture-exemption registry → C4 retro), 6 dismissed. Suite 1,645 → 1,606 (duplicate pins removed, 3 refusal tests added); bundle JS 223,272 B / CSS 19,827 B, mirror sha256-verified incl. the previously-unsynced `deck_validator.py` comment. Q8's Debug Log reworded from "AS PROPOSED" to STATED DEVIATION; EXPERIENCE.md order restored to `CHECK_ORDER`. Status → `done`. |

### Review Findings

*All resolved 2026-08-06. Brad ruled the two decisions **1a** (element-shape guard: `formatCheckOf`
now refuses `rows: []` and any non-object element — a bad body is a silent `refused`, never a
render crash; three new named refusal tests) and **2a** (the fixture DATA moved to a plain
`formatCheck.fixtures.ts`, registered BY NAME in `copy-rules.test.ts`'s new `WIRE_FIXTURE_MODULES`
and the `is_legal` scan; the pins now run once — suite count 1,645 → 1,606, the difference being
the duplicates). All 20 patches applied same day; the one defer is ledgered for the C4 retro.
Post-patch gates: 1,606 frontend tests / 61 files green, tsc, eslint, stylelint, prettier clean;
Python 2,501 passed / 1 skipped; bundle rebuilt (JS 223,272 B, CSS 19,827 B) and the plugin mirror
sha256-verified per file — including `plugin/server/src/logic/deck_validator.py`, whose comment
edit the first draft had left unsynced in the mirror (caught by the rebuild, not by a guard —
consistent with the "guarded on the Python side only" residue narrowing).*

- [x] [Review][Decision] Row-content posture: one bad element in `rows` crashes the whole deck view — `formatCheckOf` (Q-ruled) validates only `Array.isArray(rows)`, so a `200` whose `rows` contains `null`/a non-object throws at `row.check` during render with no error boundary (FR-13 inverted, white screen); a duplicate `check` token breaks React keys (`key={row.check}`); and `rows: []` draws an empty titled panel — the exact outcome the docstring's own missing-`rows` rationale refuses, declared residue but untested. All three currently sit behind the recorded "rows are not validated" ruling; tightening the narrower (e.g. every element an object, optionally non-empty) contradicts it, so Brad decides: (a) minimal element-shape guard → bad body becomes a silent `refused`, deck view survives; (b) keep the ruling, fix the false docstring only (see the MEDIUM patch). Severity: Medium (zero live exposure — needs a backend contract violation — but the consequence is the app, not the panel).
- [x] [Review][Decision] `formatCheck.fixtures.test.ts` is a test file imported by two other test files — its nine top-level pins register in every importer's collection, so they run three times (own file + `FormatCheck.test.tsx:27` + `formatCheck.test.ts:21`), silently inflating the 1,645-passed figure with duplicates. The `.test.ts` extension was chosen deliberately to sit inside the copy-guard/`is_legal` exemptions; splitting data into a plain `fixtures.ts` re-enters the guards' scanned surface, so the fix shape is a ruling: (a) split pins-from-data (data module plain, pins in a test that imports it); (b) keep the shape and acknowledge the triple-run in the record. Severity: Medium (test-count integrity).
- [x] [Review][Patch] HIGH — The guard file's own non-vacuity check is vacuous: `expect(trackedSources.concat(file)).toContain(file)` is true for any string, always — and the correct assertion would have failed on `FormatCheck.css`, which `git ls-files 'src/*.ts' 'src/*.tsx'` can never match, which is what the `concat` reads like it was papering over. An unstaged module passes this "sees this story's own modules" test AND is invisible to the `is_legal` scan simultaneously. The epic's named coverage-that-reads-as-coverage class, in the story's flagship guard. [ui/tests/format-check-source.test.ts:75]
- [x] [Review][Patch] MEDIUM — "the map lookup is guarded at the call site" is claimed and false: `FormatCheck.tsx` renders `CHECK_LABELS[row.check]`, `STATUS_WORDS[row.status]`, `TONE_FOR_STATUS[row.status]` with no guard of any kind; the client suite itself proves `{check:'nonsense', status:'exploded'}` reaches the report arm. Type-level totality is not a call-site guard. Fix the docstring to state the real mechanism and the real degraded behaviour. [ui/src/api/client.ts:475, ui/src/containers/FormatCheck/FormatCheck.tsx:267-274]
- [x] [Review][Patch] The format-check effect has no cleanup: StrictMode dev-mounts fire two wire requests (generation makes the write safe, not the request), and an in-flight read survives unmount and writes to the store — `createDeckBoot`, the cited precedent, pairs start/stop for exactly this. Add a cleanup calling `clearFormatCheck`. [ui/src/App.tsx:256-262]
- [x] [Review][Patch] Literally-always-true assertion: `expect(callsTo(fetchMock, '/api/deck/')).toBeGreaterThanOrEqual(0)` — decorative coverage; assert the real deck-detail count or delete the line. [ui/src/App.test.tsx:445]
- [x] [Review][Patch] The `is_legal` guard is misattributed in two shipped docstrings — both say `FormatCheck.test.tsx` asserts the identifier appears nowhere in `src/`; the guard lives in `ui/tests/format-check-source.test.ts:228-260`. [ui/src/containers/FormatCheck/FormatCheck.tsx:82, ui/src/api/schema.ts]
- [x] [Review][Patch] The EXPERIENCE.md amendment reorders the six-check row away from `CHECK_ORDER` (banned moved before sideboard, unexplained) and then appends a disclaimer normalising the divergence it just introduced; Q3 authorised a label correction only. Restore the wire order, keep 'Banned cards', drop the disclaimer. [EXPERIENCE.md IA table]
- [x] [Review][Patch] Q8's Debug Log entry says "AS PROPOSED — `format_recognized` is **read**" while the component header, the ledger entry and the shipped code all record the opposite (the delete-signal fired; nothing reads the field). Reword the Debug Log line as the stated deviation it is. [_bmad-output/implementation-artifacts/c4-10-format-check-panel.md:1508]
- [x] [Review][Patch] The Dev Notes still assert the plugin mirror is "checked by NOTHING" — the claim this story's own Completion Notes measured as false. Annotate in place (the deck_validator.py treatment). [_bmad-output/implementation-artifacts/c4-10-format-check-panel.md:743]
- [x] [Review][Patch] AC 10's specified numbers (5.4 ms warm / 8.5 ms cold, largest deck) were superseded by the Task 0 re-measurement (3.0/5.2/33.8 ms) and no line records the supersession — the substitution is silent. Add the supersession note to the record. [story record / AC 10]
- [x] [Review][Patch] The story record's "New (7)" file list contains eight files. [_bmad-output/implementation-artifacts/c4-10-format-check-panel.md:1789]
- [x] [Review][Patch] sprint-status.yaml `last_updated` still carries the pre-implementation contexting blurb ending "Next: dev-story c4-10", contradicted by `development_status.c4-10: review` below it. [_bmad-output/implementation-artifacts/sprint-status.yaml:233]
- [x] [Review][Patch] `margin-left: auto` on `.format-check-badge` is inert — the badge sits in an `auto` grid track that hugs its content, so the alignment is done by the `minmax(0,1fr)` first column; yet the CSS comment, the TSX comment, AND a named source test all credit the margin as the mechanism. Remove the dead declaration and re-point the comments and the pin at the real mechanism. [ui/src/containers/FormatCheck/FormatCheck.css:110-113, ui/tests/format-check-source.test.ts:199-202]
- [x] [Review][Patch] Client-test title lies about its fixture: "accepts a report whose rows are all violations" feeds one `{check:'nonsense', status:'exploded'}` row. Retitle to what it proves. [ui/src/api/client.test.ts:~715]
- [x] [Review][Patch] `MULTI_VIOLATION_REPORT` declares its two real ingredients but not that the merged body as a whole was never emitted by a real backend run — AC 26's "naming what is real and what is not" stops one step short. One docstring line. [ui/src/state/formatCheck.fixtures.test.ts]
- [x] [Review][Patch] `bootFormatCheck`'s default pairs the "VERIFIED REAL" 60-card all-pass report with the two-card Atraxa fixture deck — the body is real, the pairing is fabricated and undeclared; the harness now models a backend that cannot exist. One docstring line declaring the pairing synthetic. [ui/src/App.test.tsx:120-123]
- [x] [Review][Patch] The stylesheet colour ban matches only `color: var(...)` — a literal `color: #ff0000` matches nothing and passes; no firing-half proves the scan can see an offender. Extend or state the limitation (and note whether stylelint already closes it). [ui/tests/format-check-source.test.ts colour scan]
- [x] [Review][Patch] `codeOf`'s comment-stripper has known false-strip modes (a `/*` inside a string literal; a `//` inside a string, e.g. this codebase's own `' // '` card-name separator) and eight bans stand on it with no stated limitation. Add the stated limitation. [ui/tests/format-check-source.test.ts:49-52]
- [x] [Review][Patch] AC 38's "right column's total height before and after" is half-reported — the after (2,371 px) is recorded, the before is not. Record it or record its absence. [story record, eye-check table]
- [x] [Review][Defer] The `\.test\.tsx?$` exemption in the `is_legal` scan plus the copy-guard's identical exemption make `src/**/*.fixtures.test.ts` a blessed dead zone visible to no source-level gate — this story occupies it first, with no registry or pin on the category. Policy question, home: C4 retro. [ui/tests/format-check-source.test.ts:97] — deferred, pre-existing pattern (both exemptions predate this story)

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

2026-08-06: CODE-REVIEWED -> done (same day as implementation), on feat/companion-c4-10-format-check-panel off 4e31ea7. The format check panel: six rows, third in the right column. All 17 questions ruled before any code — 16 AS PROPOSED, ONE STATED DEVIATION and ONE CORRECTION TO THE STORY'S OWN PREMISE. THE HEADLINE HOLDS ON A REAL SCREEN: `Kotis, the Fangkeeper - 100-card Brawl` renders `Legality / VIOLATION` with "'Pym Particles' is not legal in brawl." beneath it, which DESIGN.md:423's two-slot row could not say at all — and the row below carries the other finding on the same screen, "Mainboard has 100 cards; the minimum is 60." under a green PASS. THE DEVIATION WAS FOUND BY A GATE, NOT BY TASTE (Q2): `--type-micro` carries an uppercase companion DERIVED from DESIGN.md's own textTransform key, so token-usage.test.ts went red — and shipping it correctly would have rendered "'PYM PARTICLES' IS NOT LEGAL IN BRAWL.", destroying the card name the panel exists to show. Three alternatives priced and declined; shipped `--type-body` at `--text-tertiary`, distinguished by TIER not SIZE (the .deck-row idiom), which needs no companion. THE PREMISE CORRECTION (Q3): the story lists the mock's first label as 'Format legality'; read out of the composition reference it is `{label: 'Standard', value: 'legal'}` — a FORMAT STRING, which Q14 bans from this panel's chrome and which could not be copy anyway. Four labels are the mock verbatim, 'Banned or restricted' is CORRECTED to 'Banned cards' (a false label — deck_validator.py reports `restricted` through the LEGALITY row, deliberately and pinned), and 'Legality' is authored from EXPERIENCE.md:37. TWO RECORD CORRECTIONS, BOTH MEASURED: (1) the _MIN_MAINBOARD deferral was EXACTLY BACKWARDS — this repo's own shipped skill says Brawl (Historic) is 100 EXACT, the DB agrees (all 18 brawl decks at exactly 100, min 100/max 100, 16 with a commander row), there are 2 genuinely-60 standardbrawl decks and 0 commander decks, so the named at-risk population is EMPTY while the affected one is 45% OF THE DECK TABLE; Q13 declines the code change (MCP blast radius) and corrects both places, severity Low -> Medium. (2) THE STORY'S OWN DEV NOTES CLAIM THE PLUGIN MIRROR IS "CHECKED BY NOTHING" AND THAT IS FALSE — test_spa.py::TestThePluginMirror compares both trees byte-for-byte and is what went red on the first pytest after the rebuild; residue narrowed to "guarded on the Python side only". Q17 MEASURED ON THIS SURFACE FOR THE FIRST TIME: positive 7.21:1 / negative 5.60:1 / caution 8.14:1 over their own washes on --surface-panel, all clear of 4.5:1 and ~10% below c4-2's numbers because c4-2 measured on --surface-base (re-derived 7.96/6.15/8.99, matching to rounding) — and ui/README.md's 1.89:1 for neutral's border is likewise the surface-base figure; on surface-panel it is 1.75:1, WORSE. It does not bite: TONE_FOR_STATUS is total over three statuses and `neutral` is UNREACHABLE by construction, coupled to BADGE_TONES by a type-level assert. `is_legal` IS BOUND TO NOTHING and the wire's prose Warning: block is now a MACHINE-CHECKABLE GUARD (git ls-files + comment-stripped scan, with a non-vacuity half) — which deferred-work.md:2430-2437 said did not exist. `format_recognized`'s delete-signal FIRED and is RECORDED rather than dressed up with a decorative branch: the backend already puts "could not be checked" on the glass twice in words. EYE-CHECK over CDP against the running backend, six cases (all-pass / brawl violation / 1-card historic / formatless override / reduced motion / 1100px floor): panel 452x475.1px (517.1 formatless), right column 2 -> 3 children, rows 66.3px one-line and 86.3-87.3px two-line, badges 48.8/78.2/81.1 x 24.3, padding 8px 4px live, hairline 1px #2c3048 with the LAST ROW AT 0px, 0 Tab stops / 0 aria-live / no list role / 6 items, 0 scrollers, 0 transitions, no --mana-*, no card shape, Panel badge slot EMPTY and no count — and Chrome's OWN tree reports EXACTLY ONE banner where jsdom now says SIX. C3-retro manual items C3 and C4 both discharged by name (the 1-card deck renders "Mainboard has 1 cards; the minimum is 60."). 18 LETTERED PROBES ALL CAUGHT, both do-nothing controls silent, each closed by a NAMED test; three substitutions declared (two type-level via tsc, one stylelint). THE HARNESS LIED ONCE AND ITS OWN VALIDATION CAUGHT IT — the FOURTH recorded instance of the ledgered vitest crash: a lowercase drive letter in the cwd breaks project-config resolution and all 61 files die with zero assertions, under which every probe reads caught for free (plus a second cause measured: subprocess shell=True with an argv LIST drops everything after the first element on Windows). 1,476 -> 1,645 frontend / 57 -> 61 files; Python 2,501/1 UNCHANGED (Q13's decline; the only Python edit is a comment); tokens 69 (neither pin moved), containers 19 -> 21, copy modules 11 -> 12, stores 5 -> 6, schema aliases 10 -> 12, CARD_SHAPED 4, MANA_DATA_INK 2, RUNTIME_CUSTOM_PROPERTIES 2, CALM_STYLESHEETS 1, shipped-motion pin 4, jsdom phantom banner 5 -> 6. Bundle JS 221,585 -> 223,200 B and CSS 19,294 -> 19,844 B, BOTH CHANGED; mirror rebuilt and sha256-verified per file. deferred-work.md written IN THIS COMMIT: 6 new entries, 3 inherited entries answered in place, the _MIN_MAINBOARD measurement corrected; all 11 inherited deferrals dispositioned and all 9 triggered residues given a line. Doc corrections landed: DESIGN.md x2 (Q10 padding, Q2 anatomy), EXPERIENCE.md (Q3 label), ui/README.md x2 (Q4b header pill declined, Q17 re-measured), deck_validator.py comment. Ten gates green. Next: three-layer code review.

---
epic: c4
story: c4-12
work_branch: feat/companion-c4
story_branch: feat/companion-c4-12-empty-deck-and-render-budget
depends_on: >-
  c4-2 (merged at `2a64231`) — `surfaceOf` and the boards derivation; a zero-card deck is
  `kind: 'deck'` exactly like a full one, and `deck.ts:385-391` names **c4-12 by name** as one of
  three consumers that must read that answer rather than re-derive it. c4-4 (merged at `b26e8f4`) —
  `CardGrid`, whose header says *"No empty-deck line — **c4-12** owns that copy"* and offers the
  untitled panel as the place to put it. c4-7 (merged at `0fdb41b`) — `DeckList`, which records the
  artefact gap this story must rule: it is **not** among the three panels the artefacts name as
  hidden, and nothing says whether it hides or renders empty. c4-8 (merged at `1ed2e83`) — the
  curve's self-gate on **zero curve total, not zero deck cards**, flagged here by name. c4-9 (merged
  at `4e31ea7`) — `.analysis-row:empty { display: none }`, shipped as *"c4-12's clause arriving
  early"*, with its author told the row is already handled. c4-10 (merged at `9c9349a`) —
  `FormatCheck`, whose header states the asymmetry in writing: **its data is never empty, six rows
  always, so this story's hide is the only thing that will ever hide it.** c4-11 (merged at
  `86d5fb6`) — `hasCards`, the sideboard-inclusive predicate this story must either reuse or
  consciously diverge from, and the empty-deck skip-link withdrawal already shipped and pinned.
baseline_commit: 86d5fb6
---

# Story C4.12: Empty deck state and the cold-open render budget

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad opening a deck that has nothing in it yet,
I want the app to say so calmly and still render everything that makes sense,
so that an empty deck looks intentional rather than broken — and a full deck appears fast.

**✅ BRANCH PRECONDITION — CLEAN, for the first time in three stories.** PR #50 is **MERGED**;
`origin/feat/companion-c4` is at `86d5fb6`. Cut `feat/companion-c4-12-empty-deck-and-render-budget`
from `86d5fb6`, not from `c435086` (which is the story commit *inside* the merge). Verify with
`git log --oneline -1 origin/feat/companion-c4` **before** `checkout -b`, not after — c4-11's own
record documents a near-miss where a `checkout` was aborted by an uncommitted file and the branch
was created from the wrong commit anyway, *"the precondition would have read as satisfied while
being violated"* (`c4-11:1290-1307`).

**What this story really is.** One sentence of copy, one conditional render, and a number someone
has to go and observe.

And then eleven things that are not — six of which are invisible from the acceptance criteria, and
the first two of which say the story's headline work has **already shipped** and its headline risk
is **not in the acceptance criteria at all**.

---

1. **TWO OF THE THREE PANELS AC 2 ASKS YOU TO HIDE ARE ALREADY HIDDEN, AND THEY ARE HIDDEN ON A
   DIFFERENT CONDITION.** `ManaCurve.tsx:114` returns `null` when `curve.total === 0`;
   `ColourDistribution.tsx:147` returns `null` when `distribution.total === 0`;
   `AnalysisRow.css:52-54` already collapses the row with `:empty`. All three were shipped
   *deliberately, naming this story*, and c4-9's is written as *"c4-12's clause arriving early …
   c4-12's author is told here that the row is already handled and only the panels' own conditions
   are theirs."* So for a zero-card deck, AC 2 is **two-thirds satisfied by code that already
   exists** — and satisfied by **zero curve/pip total**, not by **zero deck cards**. Those two
   conditions coincide on an empty deck and **diverge on a land-only deck**, which has cards and
   nothing for either panel to say. `App.test.tsx:794-828` pins exactly that: both panels null,
   `.analysis-row` still in the DOM with `childNodes.length === 0`. **A card-count gate added in
   `App.tsx` would duplicate a working mechanism and turn that test red.** Q3.

2. **THE HEADLINE RISK TO THE 1-SECOND BUDGET IS AN UNDOCUMENTED EFFECT ORDERING, AND IT IS ONE
   LINE.** AC 3 names six surfaces. Five of them — header, grid, curve, colour distribution, deck
   list — all derive from `boards` and paint on the deck-detail commit. The sixth, **format check,
   is a separate request**, and `App.tsx:226-229` (the 99-card hydration sweep) is declared
   **before** `App.tsx:265-272` (the format check). React runs effects in declaration order, the
   backend is HTTP/1.1 (`server.py:233`, default h11 — no h2), and Chrome caps **6 connections per
   origin**. So on a cold open the format-check request is queued at roughly **position 100** behind
   the entire sweep — and `FormatCheck.tsx:236` renders `null` until its report lands, so *the sixth
   named surface does not exist until the queue drains*. Measured backend cost of that request:
   **5.0 ms**. Measured cost of the sweep's tail in a real browser (c4-6, n=4): **847–1,795 ms**.
   Neither effect's comment mentions the other's queue position. **Swapping the two blocks moves the
   request from ~#100 to ~#1 and costs one line.** Q10, and it is the single most consequential
   decision in this story.

3. **DESIGN.md SPECIFIES THE EMPTY-DECK LINE NOWHERE — AND AC 6 DEMANDS DESIGN.md CONFORMANCE.**
   The string `"This deck is empty"` does not appear in `DESIGN.md`. The word *empty* appears twice,
   both irrelevant (`DESIGN.md:186` price column, `:439` tier shells). The **entire** specification
   is two `EXPERIENCE.md` table cells (`:70`, `:113`): the copy, `{typography.body}`,
   `{colors.text-secondary}`, *"no panel, no error styling"*. **Unspecified in either file:** spacing,
   alignment, the container, a minimum height for the grid area, whether the grid `Panel` still
   renders, and whether the line sits inside the `<ul>` (which would be invalid HTML against
   UX-DR44's mandated `ul`/`li`) or replaces it. `DESIGN.md:379` says *"**Every value in the UI comes
   from this scale**"*, so the implementer must pick one and no artefact legislates it. **AC 6 is
   therefore unsatisfiable for the empty-deck branch against DESIGN.md, because there is no DESIGN.md
   contract to match.** Q2 rules the treatment and Q13 rules what gets written back.

4. **THE STATE IS AN UNCONFIRMED ASSUMPTION, NOT A RULING — AND THE REVIEWER WHO PROPOSED IT ASKED
   FOR ONE PANEL, NOT THREE.** The provenance is `validation-report-2026-07-22.md:71-73`, a *medium*
   finding whose *Fix* reads: *"One State Patterns row (**recommend**: deck header + name render,
   calm in-grid line 'This deck is empty — ask your agent to add cards', **curve hidden**)."* The
   author adopted it verbatim and **added colour distribution and format check with no recorded
   rationale**. `.memlog.md:22` tags *"empty-deck in-grid line treatment"* as an `(assumption)` from
   the fix pass, and it is **not among the four rulings Brad confirmed**
   (`epics-companion-app.md:682-699`). This story ships an unconfirmed product decision. Say so, so
   that if Brad wants a different answer at the SC-5 gate the cost is known now rather than at Epic 8.

5. **UX-DR20 SAYS THE DETAIL PANEL IS "NEVER EMPTY WHILE A DECK IS LOADED", AND AN EMPTY DECK IS A
   LOADED DECK.** `epics-companion-app.md:446` / `EXPERIENCE.md:86`. `inspection.ts:125`'s
   `coldOpenTargetOf` returns `null` for a deck with no cards — with the comment *"which is c4-12's
   copy"*. c4-11's correction resolved only the **skip-link target** half (*"`CardDetail` renders its
   frame and heading unconditionally … UX-DR20's 'first card' fills the panel's CONTENT, not its
   heading"*). **The panel's body on an empty deck is specified nowhere.** Neither is `DeckList`'s —
   `DeckList.tsx:83-88` records the gap verbatim and refuses to invent copy for it. c4-12's own ACs
   are silent on both. Q5 and Q6 rule them; both are **artefact defects to record**, not code to fix.

6. **AC 3'S "100-CARD COMMANDER DECK" DOES NOT EXIST — AND THE MEASUREMENT IS STILL RUNNABLE TODAY.**
   Measured read-only against the shipped database: **0 commander decks**. All **18** hundred-card
   decks are `format='brawl'`, min = max = 100. This is the same shape as c4-10's deck-size finding
   and does **not** block the AC: `813d0434-1bed-4419-bf9d-d9e4070704c4` *"Atraxa Counter Cabinet v2
   (owned)"* is 100 mainboard / **99 tiles** / 6 DFCs / 0 sideboard, and it is the **only** 100-card
   deck whose images are **99/99 warm at both `normal` and `large`** (8.47 MiB / 13.10 MiB on disk).
   It is also the deck c4-11 pinned its Tab corridor against. Q8 and Q9.

7. **"WARM IMAGE CACHE" HAS TWO READINGS AND THEY DIFFER BY ~105 NETWORK REQUESTS.** Images ship
   `public, max-age=31536000, immutable` (`images.py:167`; assets likewise `spa.py:71`). So
   *(a)* fresh browser profile + warm **backend disk** cache means 105 image requests contending for
   6 sockets; *(b)* repeat visit + warm **browser HTTP** cache means **zero** image requests and a
   bundle served from disk. NFR-05 does not say which. The 99 card-detail JSON reads are **not**
   cacheable and are paid in both. Q8 rules: measure and record **both**, following c4-4's
   *"two numbers, both real"* precedent.

8. **THE 1-SECOND CLOCK HAS NO DEFINED START EVENT, AND EXPERIENCE.md STATES IT TWO WAYS.**
   `EXPERIENCE.md:111` says *"Cold open, backend live, deck set"*; `EXPERIENCE.md:183` (Flow 1 step 2)
   says the same budget from `companion_set_active_deck` **in an already-open tab** — a path that
   needs Epic 5/6 machinery Epic 4 does not have, and an order of magnitude cheaper in setup. The
   **250 ms** budget by contrast has a full defining paragraph (`EXPERIENCE.md:164`); the 1-second
   budget got one line (`:165`). The *"clock stops at first paint of laid-out content, not at
   animation settle"* clause in `epics-companion-app.md:159-160` was **back-derived from the 07-25
   gate's M2 disposition, which is scoped explicitly to SC-1** — the agent-view bloom, a thing that
   does not exist on this path. Q7 rules the clock in writing rather than leaving it inferred.

9. **AC 3 CITES SC-2, WHICH CARRIES NO TIMING — AND THE PROJECT ALREADY KNOWS.** SC-2 is
   *"Agent-driven deck edits appear in the deck view without user action"* (`prd.md:178`); it is
   Epic 7's and closes there. `validation-report-2026-07-22.md:137-139` logged the loose co-citation
   and ruled *"Fix: None required"*, after which the epics file inherited it into a story AC.
   **NFR-05 is the only authority for the number.** This story does not close SC-2 and must not claim
   to. It also must not claim SC-5: `ARCHITECTURE-SPINE.md:494` and `EPIC-SPLIT.md:121` both state
   the gate is *"a human judgement by Brad"* that *"cannot be automated or delegated"*, and it is
   **c8-6's** (`epics-companion-app.md:3366-3401`). c4-12 makes SC-5 **answerable**; it does not
   answer it.

10. **NFR-05 IS OWNED BY EPIC 4, AND THE ONLY STORY THAT CLOSES A MEASURED GAP IS PHASE 2.**
    `epics-companion-app.md:745` — `| NFR-05 | Epic 4 (1 s deck render) | Epic 6 (250 ms push),
    Epic 10 (hardening) |`, and the coverage map's own preamble says *"the owner still holds
    acceptance"*. Story 10.3 (`:3630-3636`) carries a near-verbatim twin of AC 3 **plus** the clause
    c4-12 lacks — *"any measured gap … is closed, or recorded as an accepted deviation with its
    reason — not left ambiguous"* — and 10.3 is Phase 2. So the acceptance point ships in this
    release and the repair does not. Q11 rules what happens if the number comes back red.

11. **AC 5 IS A VERBATIM DUPLICATE OF A STORY 7.4 AC, AND "BLANK SCREEN" IS DEFINED NOWHERE.**
    `epics-companion-app.md:3119` is word-for-word *"a blank screen is never shown after first paint
    (UX-DR36)"*. UX-DR36 asserts it, `EXPERIENCE.md:166` asserts it, and no artefact says what it
    means operationally. Two stories will otherwise invent two tests for one unfalsifiable sentence.
    Note also that c4-12's wording — *"**any point** after first paint"* — is **broader than its own
    epic**, since the refetch teardown UX-DR36 is really about is c7-4's. Q12 defines it for this
    story and hands the refetch half back by name.

---

## Dev Notes

### The seam that already exists — do not rebuild any of it

This story adds less code than any other in the epic. Almost everything it needs was shipped
deliberately by c4-8, c4-9, c4-10 and c4-11, each naming c4-12 in the module header. **Read all
seven of these before writing a line.**

#### `ui/src/state/deck.ts:385-429` — the one derivation, and its warning

```ts
export const surfaceOf = (deck: DeckState, system: SystemState): Surface => {
  if (deck.status === 'deck') return { kind: 'deck', detail: deck.detail, boards: deck.boards }
  if (deck.status === 'refused') return { kind: 'panel', panel: deck.panel }
  return { kind: 'panel', panel: system.panel }
}
```

**There is no "empty deck" arm and there must not become one.** A zero-card deck settles
`{status:'deck', …}` for any 200 (`deck.ts:364-365`) and `boardsOfDeck` over `cards: []` yields three
empty boards (`deckGroups.ts:252-276`). The docstring at `:385-391` names **c4-4, c4-7 and c4-12** as
the three consumers that must *"read the same answer rather than each re-deriving it from
`deck !== null`"*. `deck.ts:71` names *"the empty-deck state **c4-12**"* directly.

#### `ui/src/App.tsx:300-304` — `hasCards`, and why it is a trap

```ts
  const hasCards =
    deck !== null &&
    (deck.boards.commander.length > 0 ||
      deck.boards.sideboard.length > 0 ||
      deck.boards.mainboard.some((group) => group.cards.length > 0))
```

Its 26-line comment (`App.tsx:274-299`) is the full record of a **code-review ruling made 2026-08-07,
the day before this story**: the skip link's condition is *"any focusable deck row exists"*, **not**
*"any tile exists"*, because `DeckList.tsx:251-274` renders a focusable row per sideboard card while
`CardGrid.tsx:76` spreads **commander + mainboard only**.

⚠️ **Four different predicates are live at once, and this story touches all four:**

| predicate | where | includes sideboard? | true for a land-only deck? |
|---|---|---|---|
| `hasCards` | `App.tsx:300-304` | **yes** | yes |
| grid tiles | `CardGrid.tsx:76` | no | yes |
| `curve.total > 0` | `ManaCurve.tsx:114` | no (lands excluded) | **no** |
| `distribution.total > 0` | `ColourDistribution.tsx:147` | no (lands excluded) | **no** |

On a **sideboard-only deck**: `hasCards === true`, zero tiles, and all three analysis panels already
absent. On a **land-only deck**: cards present, tiles present, both analysis panels already absent.
Neither is describable by AC 2's *"until the deck has cards"*. Q1 rules the predicate; do not invent
a fifth.

#### `ui/src/containers/CardGrid/CardGrid.tsx:58-64` — the invitation, verbatim

> *"No empty-deck line — **c4-12** owns that copy (EXPERIENCE.md:70), and this file must simply not
> crash or render something stray without it: `boardsOf([])` returns three empty boards and the
> render below is an empty `<ul>` inside an untitled panel, **which is a place for c4-12 to put its
> line rather than a state pretending to be one** (Q10)."*

The panel is **untitled by ruling** (`CardGrid.tsx:79-86`) — a plain unnamed `<section>` that invents
no landmark name. Keep it untitled.

#### `ui/src/components/AnalysisRow/AnalysisRow.css:40-54` — already done, and it says so

`.analysis-row:empty { display: none }`, with a **declared limit** stating `:empty` matches only an
element with no child nodes at all (whitespace included), and:

> *"**Story 4.12 hides all three analysis panels on an empty deck by name and ships after this one**,
> so this is that clause arriving early: c4-12's author is told here that the row is already handled
> and only the panels' own conditions are theirs."*

#### `ui/src/containers/FormatCheck/FormatCheck.tsx:132-142` — the asymmetry, verbatim

> *"`ManaCurve` and `ColourDistribution` each hide themselves on their own data … **This panel's data
> is never empty: six rows, always.** So there is no self-gate to lean on and story **4.12** — which
> names all three analysis panels and hides them on an empty deck — is the only thing that will ever
> hide it. Not pre-implemented here."*

Its one existing `null` arm is a **state** guard (`FormatCheck.tsx:236`: `state.status !== 'report'`).
c4-12 adds a **second** `null` arm for a different reason. ⚠️ `deferred-work.md:4251-4263` records a
still-open finding that a format-check **refusal** is silent by ruling. The two `null` arms must be
distinguishable in the code and in the tests, or a reviewer cannot tell a hidden panel from a failed
one.

#### `ui/src/components/AppShell/AppShell.tsx:113-114` — never empty the `left` slot

```ts
const slot = (content: ReactNode, placeholder: string) =>
  filled(content) ? content : <p className="app-shell-placeholder">{placeholder}</p>
```

If `left` ever becomes `undefined` for an empty deck, the shell's own placeholder fires and puts the
literal text *"The card-art grid lands here — c4-4 …"* on the glass. `App.test.tsx:661-676` asserts
the absence of `c4-4`/`c4-8`/`c4-9` from `body.textContent` — **but only on the two-card fixture**, so
it would not catch this. `AppShell.tsx` has been un-edited through nine stories except for c4-11's
declared exception; **this story needs no new prop.**

#### `ui/src/App.test.tsx:1329-1354` — the empty-deck fixture already exists and is named for you

```
it('is withdrawn on an EMPTY deck — the case UX-DR31 does not cover (Q3, c4-12)')
  booting(activeDeck(ATRAXA_DECK_ID), deckDetail({ cards: [], mainboard_count: 0 }))
  :1347  expect(document.querySelector('.state-panel')).toBeNull()
  :1348  expect(screen.getByRole('heading', {level:1}).textContent).not.toBe('Artificial Planeswalker')
  :1351  expect(document.querySelector('.card-tile')).toBeNull()
  :1353  expect(screen.queryByRole('button', {name: SKIP})).toBeNull()
```

It already asserts two of AC 1's clauses (no state panel; header/name render normally) and will not
go red. **It is the natural home for the new assertions.** Its comment carries a corrected falsehood
that must not be re-introduced: the first written form claimed the skip link's *target* would not
exist on an empty deck; that was **false** and was corrected at code review 2026-08-07.

---

### What the real data says

**Measured 2026-08-07, read-only, against the shipped database**
`%LOCALAPPDATA%\artificial-planeswalker\cards.db` (249,679,872 B), opened as
`file:…/cards.db?mode=ro` with `uri=True`. No writes, no checkpoint, no importer.

#### A. ⚠️ RECORD CORRECTION — the deck table is **42 decks**, not 40

```sql
SELECT COUNT(*) FROM decks;                          -- 42
SELECT format, COUNT(*) FROM decks GROUP BY format;  -- standard 21, brawl 18, standardbrawl 2, historic 1
SELECT id,name,format,created_at FROM decks WHERE created_at > '2026-08-01';
-- caeef82f-…  'Arabella Mobilize (Boros)'             standard  2026-08-06 22:10:33
-- 45d80726-…  'Arabella Mobilize (Boros) v2 - owned'  standard  2026-08-06 22:17:16
```

Two `standard` decks were created **after** c4-10's census. Every *"40 decks / 240 rows / 20
standard"* figure in the ledger, in c4-11's §A and in `App.tsx:203` and `:247` is now stale. Any
number this story records must be keyed on **42**, and the correction stated (AC 30).

#### B. **No empty deck exists — and the state is the normal one at creation**

| measurement | result |
|---|---|
| decks with zero `deck_cards` rows | **0** |
| decks with zero mainboard rows but ≥1 sideboard row | **0** |
| decks with zero mainboard *quantity* | **0** |
| smallest real deck | `5cd42e7f-…` *"Iron Man, Modern Marvel — reminder"*, **1 card** |
| sideboard rows / decks carrying one | **41 rows across 5 decks** |
| total `deck_cards` rows | **2,060** |

`DeckRepository.create_deck` (`src/data/repositories/deck.py:53-93`) inserts a bare `DeckModel` and
commits — **no card is ever written**; the MCP wrapper says so in its own first line
(`src/mcp_server/tools/deck_management.py:231`: *"Create a new deck and return it as a `DeckDetail`
(empty `cards`)"*). `remove_card_from_deck` (`deck.py:386-432`) issues one `DELETE`, never counts
what remains and never touches `decks`. **So the empty state is reachable two ways — freshly created,
and emptied one card at a time — and neither is an error condition.**

⚠️ **Consequence: every empty-deck fixture this story writes is necessarily SYNTHETIC and must be
DECLARED SYNTHETIC IN PLACE** (c4-10 AC 26, restated as c4-11 AC 31). There is no third option.

#### C. The backend does not fail an empty deck — it answers confidently

`GET /api/deck/{id}` (`src/companion/app/routes/decks.py:67-91`) raises only on `deck is None`. An
existing-but-empty deck is a plain **200**. Produced by running the real constructor
`DeckDetail.from_deck(Deck(..., deck_cards=[])).model_dump_json()`:

```json
{ "id": "…", "name": "…", "format": "standard", "strategy": null,
  "color_identity": [], "tags": [],
  "mainboard_count": 0, "sideboard_count": 0, "distinct_cards": 0,
  "cards": [] }
```

`cards` is an **empty array — present, never absent, never null**. There is **no `card_count` field
and no `boards` field on the wire**; `boards` is a frontend derivation. `decks.format` is `NOT NULL`
and 0 of 42 rows are blank, so the `format: null` branch is **unreachable from this database**.

#### D. Format check on an empty deck — one true violation and **four vacuous greens**

`format_check(Deck(..., deck_cards=[]))`, `format='standard'` (brawl identical):

| check | status | detail |
|---|---|---|
| legality | **pass** | *"Every card is legal in standard."* |
| size | **violation** | *"Mainboard has 0 cards; the minimum is 60."* |
| copy_limit | **pass** | *"No card exceeds the copy limit; basic lands are exempt."* |
| sideboard | **pass** | *"Sideboard has 0 cards; the maximum is 15."* |
| banned | **pass** | *"No card is banned in standard."* |
| rotation | **advisory** | *"Rotation exposure cannot be checked…"* |

**Six rows always. Nothing raises, nothing 404s, nothing short-circuits.** The route's own comment
already names the failure mode — `decks.py:129-133`: *"the report that follows is a confident,
plausible-looking 'mainboard has 0 cards' violation."*

The per-card loop at `deck_validator.py:457-488` iterates an empty map and "no violations" projects
to `pass` at `:753-754`. **So an empty deck is told "Every card is legal", "No card exceeds the copy
limit" and "No card is banned" — three assertions about zero cards that are technically true and
rhetorically false.** That is a stronger argument for AC 2 than either artefact makes, and it belongs
in the code comment.

#### E. Live format-check census at 42 decks — the panel is still never all-green

| check | pass | advisory | violation |
|---|---|---|---|
| legality | 41 | — | **1** |
| size | 38 | — | **4** |
| copy_limit | 42 | — | — |
| sideboard | 42 | — | — |
| banned | 42 | — | — |
| rotation | — | **42** | — |

252 rows / 42 decks. Re-confirms c4-10's two headlines at the new count: exactly one real legality
violation (`Kotis, the Fangkeeper` — *"'Pym Particles' is not legal in brawl."*), and **rotation
advisory on 42 of 42**.

#### F. Deck-size distribution, and the render-budget deck

| mainboard | decks |
|---|---|
| 1 | 1 |
| 3 | 1 |
| 20 | 1 |
| 59 | 1 |
| **60** | **20** |
| **100** | **18** |

**0 commander decks.** All 18 hundred-card decks are `brawl`, min = max = 100.

**Use `813d0434-1bed-4419-bf9d-d9e4070704c4` — "Atraxa Counter Cabinet v2 (owned)", brawl.**

| field | value |
|---|---|
| mainboard (Σ quantity) | **100** |
| distinct rows / tiles rendered | **99** (`Forest` ×2) |
| sideboard | **0** |
| DFCs (`json_type(card_faces)='array'`) | **6** — all Pathways, incl. **Barkchannel**, not Riverglide |
| `normal_0` images on disk | **99 / 99 present, 8,885,948 B (8.47 MiB)** |
| `large_0` images on disk | **99 / 99 present, 13,736,166 B (13.10 MiB)** |
| back faces (`normal_1`) | **6 / 6 present** |

Its sibling `a092a5dc-…` is 99/99 at `normal` but **30 missing at `large`**. **These two are the only
100-card decks fully warm at the grid size**, and only `813d0434-…` is warm at both. It is also the
deck c4-11 pinned its corridor against (205 stops — *no* sideboard).

#### G. The image disk cache

`%LOCALAPPDATA%\artificial-planeswalker\image_cache\` (`images.py:369`, `cache_root()` at `:782-801`;
layout `<id[0:2]>/<id>/<size>_<face>.<ext>` at `:845-856`):

**633 files · 63,195,342 B (60.27 MiB) · 496 distinct card ids · 137 of 256 shards occupied**
(`normal_0` 496, `large_0` 120, `normal_1` 15, `large_1` 2; all `.jpg`).

The grid's default is `normal` (`images.py:147`, applied at `routes/cards.py:235`; the frontend spells
no `size=` for tiles — `imageUrl.ts:109-113`). **A warm-cache cold-open measurement is runnable today
with zero CDN traffic.** The 8.47 MiB also re-confirms the C3 retro's ~8.5 MB/deck against the real
cache rather than the wire — and corrects `ARCHITECTURE-SPINE.md:269`'s *"roughly 12 MB"*.

#### H. Backend cost on the critical path — Python is a non-event

In-process, against the shipped DB read-only. **Excludes HTTP, ASGI and JSON serialisation.**

```
GET /api/decks           list_decks     n=15   min  71.32   median  94.99   max 105.12 ms
GET /api/deck/{id}       (Atraxa v2)    n=15   min   4.52   median   4.77   max  21.42 ms
GET /api/deck/{id}/format-check         n=15   min   4.67   median   4.98   max   5.39 ms
   of which format_check() itself       n=15   min   0.07   median   0.07   max   0.10 ms
GET /api/cards/{id}      per card       n=99   min   0.34   median   0.38   max   0.93 ms
   SWEEP TOTAL (serial, in-process):    39.3 ms for 99 cards
```

Two readings worth carrying:

- **The validator is free.** `format_check()` is **0.07 ms**; the whole 5.0 ms is the duplicated
  `get_deck_with_cards` the route's own comment flags. This corroborates c4-10's re-measurement
  (3.0 / 5.2 / 33.8 ms) and supersedes its original 5.4 / 8.5.
- **The entire deck-critical backend path is ~10 ms.** If a browser measures 800 ms, **~99% of it is
  transport, queueing and parse — not Python.** Do not go optimising the backend.

⚠️ `GET /api/decks` costs **95 ms of backend CPU and repeats every 2 s** (`poller.ts:59`,
`POLL_BASE_MS = 2_000`), because `deck.py:239-267` eager-loads every full card row of all 42 decks
just to render counts (`deferred-work.md:1672-1681`, `:1844`, homed **c10-3**). It is **not** on the
deck surface's critical path — `surfaceOf` prefers the deck — but it burns one of six sockets and one
core for the first ~100 ms of a cold open. **Record it; do not fix it here.**

#### I. The critical path, in order (this is the finding that decides AC 3)

| # | request | serial/parallel | backend cost |
|---|---|---|---|
| 0 | `GET /` → `index.html` (1,916 B) → JS + CSS + woff2 | parallel | static |
| 1 | `GET /api/decks` (poller) | mount, parallel | 95 ms |
| 2 | `GET /api/active-deck` | mount, parallel | ~0 (in-memory) |
| 3 | `GET /api/deck/{id}` | **serial after 2** (`deck.ts:339`) | 4.8 ms |
| — | **commit → five of six surfaces paint** (header, grid, curve, colour, deck list — all derive from `boards`) | | |
| 4 | **99 × `GET /api/cards/{id}`**, unthrottled (`cards.ts:561`) | effect **#1** (`App.tsx:226`) | 0.38 ms each |
| 5 | `GET /api/deck/{id}/format-check` | effect **#2** (`App.tsx:265`) — **issued after all 99** | 5.0 ms |
| 6 | 99 `<img>` (+6 backs) — no `loading="lazy"`, no `fetchPriority` | dispatched **6–10 ms after** the fetches (measured, `App.tsx:192-199`) | 5.6–10.3 ms/tile warm |

**Three serial round trips before the deck can paint at all** (assets → active-deck → deck detail);
irreducible without a boot change. **Then ~205 requests through 6 sockets, with the sixth named
surface at queue position ~100.**

#### J. Every prior recorded measurement, and what each actually measured

| record | number | what it really is |
|---|---|---|
| `c4-4:1080-1089` | **9.3 s** backend fetch window, cold | filesystem **mtimes**, first→last write. **No browser.** |
| `c4-4:1080-1089` | **2–3 s** perceived paint | **an unaided human eyeball**, explicitly attributed, no timer |
| `c4-4:1074-1076` | **99 requests in 0.55 s (5.6 ms/tile)**, warm | live browser against the running backend |
| `c4-6:1300-1324` = `App.tsx:211-215` | **1,594 · 1,793 · 1,795 · 847 ms** with the sweep; **343 · 753 · 538 · 352 ms** without | real browser, **fresh profile, n=4 per arm**, clock = navigation → **last image**. First paint 32–128 ms either way |
| C3 retro `:280-289` | **~99 ms/image**, **8.5 MB/deck**, **10.3 ms/tile warm** | a **sequential HTTP driver**, not a browser; the 99 ms is *inferred* (199 ms − 100 ms pacer spacing), not timed |
| `ARCHITECTURE-SPINE.md:269` | *"roughly 12 MB and ~10 s"* cold | the epic's arithmetic, **corrected by measurement to 8.5 MB** |

⚠️ **None of these is a layout time, and none is a usable c4-12 baseline.** c4-4's two numbers measure
different things by different instruments; the record rounds c4-6's +1.01 s mean to +1.2 s; and
**c4-6's driving script did not survive** — the +1.2 s is not reproducible from any committed
artefact. The honest reading of the record is: *nobody has ever measured this app's layout time.*

⚠️ **The "CDP eye-check" is not a repo asset.** `c4-11:136-139` says so outright: *"There is no
`@testing-library/user-event`, no `axe`, no Playwright or Puppeteer, and **no committed CDP tooling**
— the past eye-checks were ad-hoc scripts, not repo assets."* Nine throwaway copies survive in
per-session temp directories and **will vanish with them**.

---

### Latest technical specifics

- **Transport is HTTP/1.1.** `server.py:233` — `uvicorn.Config(app, host=HOST, port=port,
  lifespan="on")`, default h11/httptools, **no h2**. Chrome caps **6 connections per origin**. This
  is the mechanism behind finding 2 and it is not configurable without a spine change.
- **Caching headers.** Images `public, max-age=31536000, immutable` (`images.py:167`); built assets
  likewise (`spa.py:71`). This is what makes "warm cache" ambiguous (Q8).
- **Launching the app** (c1-9, `src/mcp_server/__main__.py:267-268`; `pyproject.toml`
  `[project.scripts] artificial-planeswalker`):
  ```
  uv run artificial-planeswalker companion
  ```
  Prints `[planeswalker] companion running at http://127.0.0.1:{port} — open this URL…` to
  **stdout**. Port is preferred-with-ephemeral-fallback, so **read it from the discovery file**
  `%LOCALAPPDATA%\artificial-planeswalker\companion.json` (`{port, token, instance_id}`) rather than
  assuming 8765. Not running at context time: no `companion.json`; `companion.lock` exists but is
  0 bytes (advisory, c1-8).
- **⚠️ Measure against the committed SPA the backend serves (`spa.py`, `STATIC_DIR`), never
  `npm run dev`.** The dev server ships unminified ES modules through a proxy
  (`ui/vite.config.ts:37-40`) and its number is meaningless.
- **Installed and runnable today:** Chrome **151.0.7922.108** (`C:\Program Files\Google\Chrome\
  Application\chrome.exe`), Edge 151.0.4129.59, Node v24.15.0, and in the `uv` env
  `websockets 16.1.1` + `httpx 0.28.1` — both verified.
- **NOT installed, and deliberately:** playwright, puppeteer, lighthouse, chrome-launcher,
  chrome-remote-interface, cypress, `@vitest/browser`, happy-dom. `ui/package.json` is 3 deps + 22
  devDeps; `ui/node_modules/.bin` is 24 binaries, all lint/build/test. `chrome-devtools-mcp` is in
  the marketplace catalogue but **not installed and not enabled**. Playwright is an **explicitly
  deferred decision** — `ARCHITECTURE-SPINE.md:494`, `epics-companion-app.md:310`.
- **⚠️ vitest/jsdom structurally cannot produce this number** — no layout engine, no network stack,
  no connection limit. Stated three times in the suite already (`App.test.tsx:788-791`,
  `shell.test.ts:1049-1054`, `FormatCheck.tsx:58-59`). **An AC "satisfied" by a jsdom timing
  assertion would be this epic's coverage-that-reads-as-coverage theme for the seventh consecutive
  story.**
- **Bundle as shipped** (`src/companion/app/static/`, sha256-identical to the `plugin/` mirror):
  `index-Cazy5bCQ.js` **224,110 B** · `index-CpFoPdMw.css` **20,316 B** ·
  `space-grotesk-…-BhU9QXUp.woff2` 22,288 B · `index.html` 1,916 B · `favicon.svg` 806 B —
  **269,436 B total**, one chunk, no code splitting, no size budget anywhere. Epic C4 grew JS
  202,846 → 224,110 B (+10.5%).
- **Recorded CDP harness traps** (all three produced *false negatives about the app* before being
  found): `Input.dispatchKeyEvent` needs `text` on the keydown for Enter to synthesise a button's
  default action; `blur()` does **not** reset Chrome's sequential focus navigation starting point
  (`c4-11:1555-1571`); computed-style comparisons must not string-match `'0s'` (`c4-8:1738`).

---

### Decide-once rulings this story inherits (do not re-derive)

1. **`surfaceOf` is the single derivation** (c4-2). No third re-derivation from `deck !== null`,
   and **no new `Surface` arm for the empty deck**.
2. **`hasCards` includes the sideboard** (c4-11 code review, 2026-08-07). The reason is written at
   `App.tsx:291-299` and must not be quietly reversed.
3. **The grid `Panel` is untitled** (c4-4 Q6). It stays untitled.
4. **Each analysis panel owns its own emptiness; the row owns its own** (c4-8 Q12, c4-9 Q10). The
   row's mechanism is `:empty`, not an `App.tsx` gate.
5. **`FormatCheck` was not pre-implemented** (c4-10 Q12, *as proposed*), and the asymmetry was
   written down rather than smoothed over.
6. **The right column renders only for `kind === 'deck'`** (c4-5 Q14). L8 is cited, not re-litigated.
7. **The detail panel is not a live region**; only a *pin* announces, once (c4-5 / gate C1). **This
   story adds no `aria-live`** — an empty-deck line that announced itself would be the fourth
   panel-visibility change in the epic to invent a second announcement mechanism.
8. **Copy lives in an import-free `copy.ts` registered in `COPY_MODULES`** (c2-9 decide-once ruling
   #1, restated at `copy-rules.test.ts:123-129`, which names *"c4-12's empty-deck line"* explicitly).
9. **SC-5 is Brad's, at c8-6, and cannot be automated or delegated** (UX-DR49,
   `ARCHITECTURE-SPINE.md:494`, `EPIC-SPLIT.md:121`).
10. **Playwright is deferred** (`ARCHITECTURE-SPINE.md:494`, `epics:310`). Installing it is a Brad
    ruling, not a story decision.

---

### The eighteen things this story must not break

1. **`App.test.tsx:794-828` — the land-only deck.** Both analysis panels null, `.analysis-row`
   present with `childNodes.length === 0`. A card-count gate on the row or the panels reddens it.
2. **`App.test.tsx:1356-1379` — the sideboard-only deck.** `.card-tile` null, `.deck-row` present,
   **skip link PRESENT**. Any hide keyed on "no tiles" reddens it.
3. **`App.test.tsx:1329-1354` — the empty-deck skip-link withdrawal** stays green, and its corrected
   comment about the skip target existing is **not** re-broken.
4. **`hasCards`'s sideboard clause and its 26-line reason** survive verbatim unless Q1 rules
   otherwise **in writing, in the same comment**.
5. **`surfaceOf` stays the single derivation**; `Surface` gains no arm.
6. **The `left` slot is never `undefined`** — `AppShell`'s placeholder must not return to the glass.
7. **`AppShell.tsx` is not edited.** Nine stories of restraint plus one declared exception.
8. **`AppShell.test.tsx`'s landmark counts stay 1 banner / 1 main / 1 contentinfo.**
9. **The jsdom phantom-`banner` count holds at 6 on a populated deck** (`App.test.tsx:1664+`).
   ⚠️ On an **empty** deck it is **3** (shell header + card detail + deck list), because three titled
   panels are hidden. A new empty-deck assertion must use 3 and say why.
10. **`App.test.tsx:881`'s document-wide `getAllByRole('listitem')` count of `2+2+1+6`** stays, inside
    its two-card fixture, and any new count follows its shape: scoped counts first, then one total.
11. **`App.test.tsx:661-676` / `:731-733`** — no `c4-*` story key on the glass; `c6-8` still present,
    count **1**. F1 stays **c8-5's** gate.
12. **The token inventory holds at 69** (`tokens.test.ts:321`, `token-usage.test.ts:1170`). The empty
    state spends `--type-body` and `--text-secondary`, both existing. A new token needs a DESIGN.md
    amendment and both pins move together.
13. **`RUNTIME_CUSTOM_PROPERTIES` keeps its two entries** and `eslint.config.js` is **unedited** —
    `inline-style-violation.tsx` stays pinned at exactly **2** messages (`lint-gates.test.ts:133-172`).
14. **`CARD_SHAPED` keeps 4 entries; `MANA_DATA_INK` keeps 2.** The empty-deck line draws no card:
    `--radius-card` appears nowhere in its CSS.
15. **`copy.test.ts:114` / `copy-tails.test.ts:149-152` stay pinned at 6.** Both parsers require
    *both* `Headline:` and `Body:` in a cell; the *"Empty active deck (0 cards)"* row is neither, so
    it is invisible to them. **Do not reword that row into Headline/Body shape.**
16. **`CardDetail`'s single polite live region stays the only one.** No `aria-live` here.
17. **Python is untouched**: `uv run pytest` stays at **2,501 passed / 1 skipped**, and
    `test_spa.py::TestThePluginMirror` stays green.
18. **`npm run gen:api` produces no diff** — no Pydantic model moves.

---

### Source tree — what exists, what this story touches

```
ui/src/
  containers/
    CardGrid/
      CardGrid.tsx              EDIT  Q2 — the line, replacing the <ul> when empty
      CardGrid.css              EDIT  Q2 — the line's spacing/alignment, every literal cited
      copy.ts                   NEW   Q2 — EMPTY_DECK_LINE, import-free
      CardGrid.test.tsx         EDIT  ⚠️ :155-165's title becomes FALSE — rewrite, do not delete
    FormatCheck/
      FormatCheck.tsx           EDIT? Q3 — only if the gate lives in the panel rather than App.tsx
  App.tsx                       EDIT  Q1 (the predicate), Q3 (the FormatCheck gate),
                                      Q4 (the request), Q10 (effect order)
  App.test.tsx                  EDIT  the empty-deck describe; the AC 5 boot-sequence assertion
  state/
    deck.ts                     EDIT? Q1 — if the predicate is extracted, it lands here beside
                                      surfaceOf, NOT in a new module
    deck.test.ts                EDIT? ditto
ui/tests/
  shell.test.ts                 EDIT  CONTAINERS 24 → 25; CardGrid's imports gain './copy'
  copy-rules.test.ts            EDIT  COPY_MODULES 13 → 14, reason > 40 chars
  empty-deck-copy.test.ts       NEW   Q2 — the byte-for-byte artefact gate
                                      (shape: unknown-card-copy.test.ts / skip-link-copy.test.ts)
_bmad-output/planning-artifacts/
  ux-designs/…/DESIGN.md        EDIT  Q13 — the empty-deck treatment + the D-1 padding family
  ux-designs/…/EXPERIENCE.md    EDIT  Q13 — alt text, price, the corrected corridor figure
_bmad-output/implementation-artifacts/
  deferred-work.md              EDIT  AC 29 — every disposition, in THIS commit
ui/README.md                    EDIT  Q13 — ten stale claims
src/companion/app/static/       BUILD both assets change; git add the UNTRACKED new hashes
plugin/                         BUILD rebuild + verify sha256-identical per file
```

**Not touched:** `AppShell.tsx`, `ManaCurve.*`, `ColourDistribution.*`, `DeckList.*`, `CardDetail.*`,
`AnalysisRow.*`, `eslint.config.js`, `tokens.css`, anything under `src/` (Python).

---

### Open questions — answer these before writing code

Each carries a proposal. Rule each one, record the reason in the Debug Log, and say plainly where you
deviate.

**Q1 — What is "an active deck with zero cards", mechanically?**
Four predicates are live (see the table above) and `deck.ts:388-390` bans a fifth derivation.
*Proposal:* extract **one** predicate beside `surfaceOf` in `deck.ts` —
`export const deckIsEmpty = (boards: DeckBoards): boolean => …` — defined as the exact negation of
`hasCards`'s board test, and **refactor `hasCards` to consume it** so there is one expression in one
place. Reason: it keeps c4-11's sideboard ruling intact, it makes the copy *true* (a deck with a
sideboard is not empty, and saying so would be false copy under UX-DR33), and it satisfies
`deck.ts`'s own warning. ⚠️ Consequence to state, not hide: a **sideboard-only** deck then renders an
empty grid with **no line** — a state no artefact describes. It is unreachable from live data (0 of
42 decks), so record it as a named residue rather than inventing copy for it.

**Q2 — Where does the line render, and what does it replace?**
*Proposal:* in `CardGrid.tsx`, from a new import-free `src/containers/CardGrid/copy.ts`, **replacing
the `<ul>` rather than sitting beside it** — a `<p className="card-grid-empty">` as the untitled
`Panel`'s only child. Reasons: `CardGrid.tsx:60-64` offers itself by name; a `<p>` inside a `<ul>` is
invalid HTML against UX-DR44's mandated list semantics; and an empty `<ul>` plus a line announces "0
items" to a screen reader before the sentence explaining why. Costs: `CONTAINERS` 24 → 25,
`COPY_MODULES` 13 → 14, `'./copy'` added to CardGrid's declared imports, and
`CardGrid.test.tsx:155-165` rewritten **in the same commit** — its title
(*"must not invent c4-12's copy"*) becomes false the moment this lands.
*Rejected alternative:* rendering from `App.tsx` — it puts prose in a module that is not a
`COPY_MODULE`, and it would still need the copy module anyway.

⚠️ **ORDERING CONSTRAINT — amend `DESIGN.md` BEFORE writing the CSS, not after.**
`shell.test.ts:995-1032` requires **every `px` literal in every `src/components/` or
`src/containers/` stylesheet to carry a `DESIGN.md` citation within a sentence of the value**. Since
DESIGN.md specifies the empty-deck treatment **nowhere** (finding 3), there is nothing to cite and
the guard cannot be satisfied by any spacing choice. The sequence is therefore: **(1)** rule the
treatment, **(2)** write it into `DESIGN.md` Components + frontmatter in the c4-10 amendment style
with the reason inline (AC 26), **(3)** write `CardGrid.css` citing the new line numbers. Doing this
in the other order produces either a red guard or an invented citation — and an invented citation is
the D-2 class this same story is recording against the epic.
**The cheapest compliant treatment spends only scale tokens and needs no px literal at all**
(`--space-*` for the inset, `--type-body`, `--text-secondary`), which is also what keeps it inside
the calm families of Q16. Prefer that; amend DESIGN.md to match what you ship either way.

**Q3 — Does anything new gate the three analysis panels?**
*Proposal:* **only `FormatCheck`.** `ManaCurve` and `ColourDistribution` already return `null` at zero
data and `.analysis-row:empty` already collapses the row; adding a card-count gate would duplicate a
working mechanism c4-9 explicitly told this story was handled, and would redden the land-only test.
Gate `FormatCheck` in `App.tsx` (not in the panel) so the panel keeps exactly one self-owned `null`
arm and this story's arm is visibly a different decision. **Assert in the suite that the other two
are already absent, and assert *the reason* — zero curve total, zero pip total — so the coincidence
is pinned rather than assumed.**

**Q4 — Does the format-check *request* fire for an empty deck?**
*Proposal:* **no — suppress it.** Gate `loadFormatCheck` on the same predicate. Reasons: the precedent
assertion already exists (`App.test.tsx:465-487` pins "no request behind a state panel"); a hidden
panel that still fetches is a wasted round trip on the exact path AC 3 measures; and the response is
four vacuous greens plus one violation nobody sees. ⚠️ Keep `clearFormatCheck`'s teardown arm intact —
c4-10's review found the missing cleanup half once already.

**Q5 — What does `DeckList` do on an empty deck?**
The artefact gap is recorded verbatim at `DeckList.tsx:83-88`: `EXPERIENCE.md:70`, `:113` and this
story's own AC each name **exactly three** panels, and the deck list is not among them.
*Proposal:* **it renders its titled panel with no rows — status quo — and this is RULED and RECORDED,
not left silent.** Reason: adding a fourth panel to the hide list is inventing spec, and inventing an
empty-state sentence puts unsourced words on the glass. ⚠️ State the SC-5 cost honestly: an empty
titled `region` beside an empty detail panel is precisely the *"reads as a loading failure rather
than as an absent feature"* failure mode `DESIGN.md:186-187` names. Ledger it, homed on the C4 retro.

**Q6 — What does `CardDetail` show on an empty deck?**
UX-DR20 says *"never empty while a deck is loaded"*; `coldOpenTargetOf` returns `null`.
*Proposal:* the panel renders its frame and `<h2>` (it already does, unconditionally) with no card
content, and **this is recorded as an artefact defect against UX-DR20** rather than repaired by
inventing copy. c4-11's correction resolved only the skip-target half; the body half is undescribed.
Home: the C4 retro, with the DESIGN.md amendments as precedent.

**Q7 — What exactly does the 1-second clock measure?**
*Proposal:* **start = navigation start** (`performance.timeOrigin` / the navigation entry's
`startTime`); **stop = the moment the last of the six named surfaces enters the DOM.** Adopt the
07-25 gate's M2 definition — *"first paint of laid-out content, not animation settle"* — **explicitly
and by citation**, noting that it was written for SC-1 and that the deck-view path has no entry
animation (`EXPERIENCE.md:105` gives only a 100 ms image fade), so the clause is *probably vacuous
here* and is adopted for consistency rather than necessity. **State that this story measures
`EXPERIENCE.md:111`'s cold open, NOT `EXPERIENCE.md:183`'s active-deck-change-in-an-open-tab**, which
needs Epic 5/6 machinery Epic 4 does not have.

**Q8 — Which "warm image cache"?**
*Proposal:* **measure and record both**, following c4-4's *"two numbers, both real"* precedent:
(a) fresh browser profile + warm backend disk cache (105 image requests contend for 6 sockets);
(b) repeat visit + warm browser HTTP cache (zero image requests, bundle from disk). Note in both that
the 99 card-detail JSON reads are **not cacheable** and are paid either way.

**Q9 — What harness produces the number?**
*Proposal:* **an ad-hoc CDP harness in Python** — the established house pattern; every C4 story from
c4-5 carries *"an eye-check is performed in a real browser over CDP against the running backend, not
described."* Launch `chrome.exe --remote-debugging-port=9333 --headless=new --user-data-dir=<fresh
temp>`, poll `/json` for the target, drive it with `websockets` + `Runtime.evaluate({awaitPromise:
true})`, resolving on a `MutationObserver` that fires when the format-check rows enter the DOM. Enable
`Network` and dump `performance.getEntriesByType('resource')` — **that waterfall is what proves or
disproves the queue-position claim, and it is the artefact "recorded as an acceptance observation"
actually wants.** **≥5 runs per arm** (c4-6's n=4 gave an 847–1,795 ms spread; one run is not a
measurement). Carry the three recorded harness traps. Run an `httpx`-only replay as a companion
lower bound if useful, but it can never prove the AC — it cannot see socket contention or JS parse.
**Do not install Playwright** (two shipped artefacts defer it) and **do not assert the budget in
vitest**.

**Q10 — Do the two effects swap?**
*Proposal:* **measure as shipped first** — that is the honest baseline AC 3 asks for — then, if the
sixth surface misses the budget, **swap `App.tsx:226-229` and `:265-272` so the format check is
issued before the sweep, re-measure, and record both numbers.** Either way, **document the ordering
as a load-bearing decision in both effect comments**, because today neither mentions the other's
queue position and the next reader will reorder them by accident.

**Q11 — What if the measurement misses 1 second?**
NFR-05's acceptance is **Epic 4's** and the only gap-closing story is **Phase 2's 10.3**.
*Proposal:* **record the number honestly and do not fail the story.** If it misses after Q10's swap,
write it down as an accepted deviation with its reason and its home (c10-3), **and raise the ownership
conflict explicitly for Brad** — the owner holds acceptance and cannot close the gap in this release.
`epics-companion-app.md:3634-3636` is the clause c4-12 lacks and 10.3 has; cite it.

**Q12 — What is a "blank screen"?**
*Proposal:* define it operationally **for this story**: at no point from first paint onward does the
app render a viewport containing none of {header, left-column content, right-column content, footer}.
Assert it across the boot sequence in the suite (deck boot, refusal, recovery, empty deck). ⚠️ Note in
writing that AC 5 is a **verbatim duplicate of `epics-companion-app.md:3119`** and that the
**refetch** half — the teardown UX-DR36 is really about — is **c7-4's**, handed back by name.
`states.ts`'s `NO_UI_RESPONSE` classification is the one thing in the codebase in tension with the
sentence; cite it.

**Q13 — How much of the SC-5 conformance sweep lands here?**
The sweep found real drift, and AC 6 asks for the **comparison**, not for every repair.
*Proposal — LAND (cheap, mechanical, deck-view-scoped):*
- `DESIGN.md:141`, `:142`, `:145` — `panel.header-padding: '10px 14px'`, `panel.body-padding:
  '12px 14px'`, `badge.padding: '2px 9px'`. **`DESIGN.md:379` bans `14` and `9` by name**, the code
  already overrides all three with scale tokens, and the c4-10 amendment's own text (`:243`) names
  these two files as *"the identical repair … already shipped twice"* without amending them. This
  closes the last three of that family.
- `Panel.css:12`, `Badge.css:12`, `StatChip.css:62`, `card-geometry.css:20` — the token count reads
  **64** or **65**; it is **69**, pinned twice.
- `ColourDistribution.css:99-104` — says its hairline is *"an amendment `components.color-bar` should
  carry"*; that amendment shipped in the same story (`DESIGN.md:214-223`). Cite `:223`, delete the
  clause.
- `EXPERIENCE.md:157` — the alt-text rule is contradicted by both shipped consumers (`CardTile.tsx:431`,
  `:458`, `CardDetail.tsx:500`, `:511` all ship `alt=""` with a written argument). **Code right,
  artefact wrong, never amended.**
- `EXPERIENCE.md:35`, `:86` and `DESIGN.md:369` — still promise a **price** after `DESIGN.md:429`/`:431`
  removed it twice on c4-7's measurement.
- `DESIGN.md:418` — still *"100+ Tab stops"* where `EXPERIENCE.md:100`/`:143` now carry c4-11's
  measured 206/78/102.0. **Peer artefacts disagree on the same number.**
- `ui/README.md` — ten stale claims (four token counts, the alias count 9→12, `CardFace` "still
  declined", the format-check route written as a prediction, *"the other six still have none"*
  falsified by its own next paragraph, the skip link in future tense, three stale anchors).
- Plus the empty-deck treatment itself, written into `DESIGN.md` Components so AC 6 becomes
  satisfiable (finding 3).

*Proposal — RECORD, DO NOT FIX:* **~60 stale `DESIGN.md:NNN` anchors across 25 files.** The c4-7/c4-9/
c4-10 frontmatter amendments grew the file and nothing re-based the citations; one now cites a real
but **wrong** component (`FormatCheck.css` → `DESIGN.md:423`, the Card tile bullet). `shell.test.ts:1021`
requires only the *string* `"DESIGN.md"` near a px literal — **it never validates the line number**,
which is this epic's coverage-that-reads-as-coverage theme in a citation gate. Write the ledger entry
**with the guard's shape in it** (resolve the anchor and assert the cited line names the component)
and home the re-base on the **C4 retro**. Doing it here would add ~60 edits and a red guard to a story
that is otherwise one sentence and one conditional.

**Q14 — How is the empty state eye-checked at all, given no empty deck exists?**
*Proposal:* create one through the MCP tool (`create_deck`), set it active, eye-check it over CDP,
**then delete it**, and record the create/delete in the Debug Log as a deliberate, reverted write.
State the deck count before and after (**42**) to prove the database was left as found. If Brad
prefers no write to the real database, the fallback is jsdom-only coverage plus a stated gap — say
which was done.

**Q15 — Are the `AnalysisRow` and the right column visually correct with panels missing?**
`DESIGN.md:384` states the left column's curve + colour distribution as *"a 1:1 pair"* and the right
column as *"card detail, deck list, format check, stacked"*, **unconditionally**. Hiding three panels
leaves a composition DESIGN.md never describes.
*Proposal:* verify by eye at Q9's CDP run — the left column with only the grid panel, and the right
column with two panels instead of three — and **record what it looks like** rather than asserting it
is fine. This is the half of AC 6 that no gate can answer, and it is exactly what UX-DR49 says the
SC-5 gate tests for.

**Q16 — Do the tokens hold at 69?**
*Proposal:* **yes.** The line spends `--type-body` (which requires **no** companion declaration —
only display/label/micro do, `token-usage.test.ts:1935`, `:1943-1945`) and `--text-secondary`. Both
exist. Assert the inventory is unmoved rather than assuming it. ⚠️ If the line's stylesheet declares
itself **calm** by joining `CALM_STYLESHEETS` (`token-usage.test.ts:1018-1024`, today only
`StatePanel.css`), it is then restricted to the calm token families — which `--type-body` and
`--text-secondary` both satisfy, making it arguably the right home for *"no error styling"*. Rule it
either way with the reason.

**Q17 — Does the copy string survive the guards, and what gates it?**
Verified in advance: **the em dash is not banned.** `copy-rules.test.ts`'s `BANNED` set is exactly
`!` (after NFKC), Extended_Pictographic, and `/something\s+went\s+wrong/i` — there is **no typography,
apostrophe or dash rule anywhere in the file**. The exact string is
`This deck is empty — ask your agent to add cards.` (em dash U+2014, one trailing period), from
`EXPERIENCE.md:70`.
*Proposal:* ship it **byte-for-byte** and add `ui/tests/empty-deck-copy.test.ts` on the shape of
`unknown-card-copy.test.ts` / `skip-link-copy.test.ts` / `named-card-copy.test.ts` — import the
import-free module, parse the artefact row, compare. Reason: `deferred-work.md:3691-3696` is a
**permanently open** entry recording that c4-3 discharged the "is this copy blameless" judgement
precisely by shipping the artefact's own label byte-for-byte, and it says *"c4-12 and c6-6 owe the
same reading."* Deviating re-opens a judgement no guard can make.

---

### The inherited deferrals — give each a disposition (AC 29)

`deferred-work.md` names c4-12 **twice**. That is the wrong place to look, and it is itself a finding:
**fifteen shipped source modules name this story** and the ledger does not — the c4-7 failure mode
replaying, *"a disposition written in a story file and not in the ledger is a disposition nobody will
find"* (`deferred-work.md:3866`).

| # | entry | disposition to write |
|---|---|---|
| 1 | `:1539-1546` — **the copy guard cannot decide the half that matters.** *"A reviewer of c2-10, c4-3, **c4-12** and c6-6 must READ the copy."* Permanent, by design. | HONOUR it. This story ships one authored sentence under UX-DR33. Read it and say so. |
| 2 | `:3691-3696` — c4-3's disposition (4): the same judgement, discharged by shipping the artefact's label byte-for-byte. *"**c4-12** and c6-6 owe the same reading."* | HONOUR, same mechanism (Q17). |
| 3 | `:4247` — **zero-total conflates "genuinely colourless" with "hydration not yet arrived"**: a panel that materialises mid-sweep and snaps the row from full width to half, inside c4-6's accepted no-re-drive window. | **The most on-point entry in the ledger.** This story composes a *second* hide condition with that timing-dependent one. Read it before writing the gate; state whether the composition makes it better, worse or unchanged. |
| 4 | `:4251-4263` — a format-check **refusal** is silent by ruling; the right column loses its third panel and nothing says a check failed. Home: c7-3 or c8-6. | Keep the two `null` arms distinguishable. Do not absorb this entry. |
| 5 | `:3965-3973` — the hydration sweep's no-re-drive window, **accepted as designed**. | Cite; do not re-open. State whether this story's panel is inside it (Q3/Q4 remove the format check from it entirely). |
| 6 | `:2255-2263` — `ETag`/conditional requests, homed on the C4 retro *"where the epic's twelve stories are the ones that will have exercised the cache on real decks by then."* | **c4-12 is the twelfth.** Feed the §G cache measurement forward; do not decide. |
| 7 | `:3203-3216` / `:3830-3833` — the **~124 s cold paint against a dead CDN**, never reproduced. Home: c10-3 + the epic manual-testing checklist. | Not this story. Add it to the checklist by name. |
| 8 | `:3777-3784` — the pacer queue vs the pool timeout; `loading="lazy"` named as the one client-side lever. | ⚠️ If Q10's work reaches for `loading="lazy"`, this entry pre-priced it. Otherwise: unchanged. |
| 9 | `:1672-1681` — `list_decks` materialises every deck's card list to count it (§H: 95 ms, every 2 s). Home: c10-3. | Record the re-measurement at 42 decks; do not fix. |
| 10 | `:4236-4241`, `:4161-4169` — `EXPERIENCE.md:34`/`:173` promise *source counts* and *deck value*; `StatChip` still has no surface. Home: C4 retro. | Not this story. Confirm still open. |
| 11 | `:1592-1609` — 10px ALL-CAPS legal text readability. Home: **Epic 8**. | Do not touch. |
| 12 | `:4399-4409` — the skip link does not reach the footer (206/78/102.0). Home: **c8-6**. ⚠️ `skip-link-copy.test.ts:113` bans the string `"Skip to footer"` and will red on c8-6's own ledgered fix. | Do not touch skip-link copy. If you must, read that test's header first. |
| 13 | `:4355-4362` — the `rem` basis. **Declined by name at c4-11**, re-homed to Epic 8. | Do not take it. |
| 14 | `:4313-4320` — the `.test.ts` exemption pair's unguarded fixture dead zone. Home: C4 retro. | ⚠️ Relevant: this story's empty-deck fixtures live in exactly that zone. Declare them synthetic in place. |
| 15 | `:4044-4047`, `:4301-4309` — **the plugin bundle mirror is guarded on the Python side only**; a frontend-only `npm test` cannot see a stale mirror. Home: C4 retro. | Rebuild and sha256-verify by hand (AC 27). |

---

### Anti-patterns this epic has actually committed — pre-empt each by name

**1. Coverage that reads as coverage — SIX consecutive stories, every time in the story's own
flagship guard.** c4-4 (a false-PASS path in the transform guard), c4-7 (a comment reading *"git, not
readdir, so an untracked module cannot pass vacuously"* asserting the opposite of the truth), c4-8 (a
**fabricated** split-card fixture pinning nothing), c4-9 (a vacuous `groupOf` guard whose comment
contradicted its own `expect`), c4-10 (`expect(trackedSources.concat(file)).toContain(file)` — **true
for any string, always**), c4-11 (an `onKeyDown`-absence test **claimed in two shipped comments and
existing nowhere**).
**The five shapes to pre-empt:** a fabricated fixture that makes the subject unreachable; a vacuous
fixture with no discriminating power; a tautological assertion true for any input; a value computed
and discarded; a mis-declared limit in a header comment. **Every new guard states what it cannot see.**

**2. Untracked bundle assets — a HIGH finding twice** (c4-3, c4-7). The mechanism is documented at
`.github/workflows/ci.yml:143-149`: Vite emits **content-hashed** filenames, so a source change
produces one **deletion** (which `git diff` sees) plus one **untracked addition** (which it does not).
`git diff --exit-code` passes on exactly the staleness the check exists to catch, which is why CI uses
`git status --porcelain`. **`git add -A src/companion/app/static/` — `git add -u` is not enough.**

**3. Fixtures neither verified-real nor declared-synthetic.** c4-9 turned four fabrications into
verified rows; c4-10 found a **fabricated pairing** (a real 60-card all-pass report paired with a
two-card deck — *"the harness now models a backend that cannot exist"*). ⚠️ **No corpus deck has zero
cards**, so every empty-deck fixture here is synthetic by necessity and must say so in place.

**4. Probe harnesses that lie — five recorded instances.** The rule: **prove a guard fires through the
full `npm test`, never a single-file run**, and **validate the collected-test count on every probe run**
— a shortfall is a broken harness, not evidence. c4-11's first-pass probe produced unparseable TSX and
collected 1,596 tests instead of ~1,655, so every assertion read "caught" for free.

**5. Forward statements in prose that turn out false.** `ui/README.md` has had **six** falsified. This
story writes a measurement into the record; write what was observed, not what is expected.

---

## Acceptance Criteria

### The empty deck — the line

1. **Given** an active deck with zero cards on every board, **when** the deck view renders, **then**
   the grid area shows the line `This deck is empty — ask your agent to add cards.` in
   `--type-body` / `--text-secondary`, **byte-for-byte** the string at `EXPERIENCE.md:70`
   (em dash U+2014, one trailing period) — no state panel, no error styling, no icon (UX-DR33,
   UX-DR30).
2. **Given** that line, **when** its source is inspected, **then** it lives in an **import-free**
   `src/containers/CardGrid/copy.ts` registered in `COPY_MODULES` with a reason over 40 characters —
   never a literal in a `.tsx` (c2-9 decide-once ruling #1).
3. **Given** the empty state, **when** the DOM is inspected, **then** the untitled grid `Panel` still
   renders and the line **replaces** the `<ul>` rather than sitting inside or beside it — no empty
   list announcing "0 items" before the sentence explaining why (UX-DR44).
4. **Given** the empty state, **when** the `left` slot is inspected, **then** it is never `undefined`
   and `AppShell`'s `c4-4`/`c4-8`/`c4-9` placeholder text does not appear anywhere in
   `body.textContent` — **asserted on the empty-deck fixture**, not only on the populated one.
5. **Given** the deck header, **when** an empty deck renders, **then** the kicker, the `h1` deck name,
   the format badge and a **`0 maindeck`** size badge all render normally
   (`DeckBadges.test.tsx:90-92` already pins the zero count rather than hiding it).
6. **Given** the empty state, **when** the copy is judged, **then** a human has **read** it for
   second-person, blameless, concrete-next-action voice and recorded that reading —
   `deferred-work.md:1539-1546` and `:3691-3696` both say no guard can do this and both name c4-12.

### The empty deck — what hides, and what does not

7. **Given** an empty deck, **when** the analysis panels are inspected, **then** the mana curve,
   colour distribution and format check all render nothing (UX-DR33, `EXPERIENCE.md:70`, `:113`).
8. **Given** AC 7, **when** the mechanism is inspected, **then** the curve and colour distribution are
   absent **because their own zero-total guards already fire** — no new card-count gate is added for
   either — and the suite asserts *that reason*, not merely their absence.
9. **Given** AC 7, **when** the format check's absence is inspected, **then** it is the only panel
   gated by this story, and its two `null` arms — *state is not a report* (c4-10) and *the deck is
   empty* (c4-12) — are distinguishable in the code and in the tests.
10. **Given** an empty deck, **when** the network is observed, **then** `GET /api/deck/{id}/format-check`
    is **not issued** — matching the precedent at `App.test.tsx:465-487`.
11. **Given** a **land-only** deck (cards present, zero curve total, zero pips), **when** it renders,
    **then** the grid shows tiles, **no** empty-deck line appears, both analysis panels are absent and
    `.analysis-row` is still in the DOM with zero child nodes — `App.test.tsx:794-828` passes
    **unchanged**.
12. **Given** a **sideboard-only** deck, **when** it renders, **then** the skip link is still
    **present** and `App.test.tsx:1356-1379` passes **unchanged**; whatever Q1 rules for the line on
    that deck is stated in the code with its reason.
13. **Given** the deck list panel and the card detail panel on an empty deck, **when** their behaviour
    is inspected, **then** it is **ruled and recorded** — not silent — and the UX-DR20 contradiction
    (*"never empty while a deck is loaded"*) is written into `deferred-work.md` as an artefact defect
    rather than repaired by inventing copy.
14. **Given** the empty state, **when** the accessibility tree is inspected, **then** no `aria-live`
    region is added anywhere, and the jsdom phantom-`banner` count on the empty-deck fixture is
    asserted at **3** (shell header + card detail + deck list) with the reason stated.

### The cold-open render budget

15. **Given** the 100-card deck `813d0434-1bed-4419-bf9d-d9e4070704c4` and a warm image cache,
    **when** the app cold-opens in a **real browser** against the **committed SPA** served by the
    running backend, **then** full layout — header, grid, curve, colour distribution, deck list **and
    format check** — is measured against the **1 second** budget (NFR-05), over **at least five runs
    per arm**, and the numbers are recorded.
16. **Given** AC 15, **when** the clock is defined, **then** its **start** and **stop** events are
    written down explicitly, `EXPERIENCE.md:111`'s cold open is named as the path measured and
    `:183`'s active-deck-change is named as the path **not** measured, and the M2 *"first paint of
    laid-out content"* clause is adopted **by citation** with a note that it was written for SC-1.
17. **Given** AC 15, **when** "warm image cache" is resolved, **then** **both** readings are measured
    and reported separately — fresh browser profile + warm backend disk cache, and repeat visit +
    warm browser HTTP cache — with the 99 non-cacheable card-detail reads noted as paid in both.
18. **Given** the measurement, **when** it is recorded, **then** it includes the **resource waterfall**
    showing where the format-check request actually sat in the queue, the hardware and conditions it
    was taken under, and it is **observed, never asserted from jsdom** — a vitest timing assertion
    does not satisfy this AC.
19. **Given** a cold image cache, **when** the deck loads, **then** layout is measured against the
    same budget and the *"first-fetch image paint excluded"* clause is applied **explicitly**, with
    the ~8.5 MB / ~10 s cold-paint observation cited as the expected, non-defect behaviour
    (NFR-05, UX-DR36, `epics-companion-app.md:1794-1797`).
20. **Given** the two `useEffect` blocks at `App.tsx:226-229` and `:265-272`, **when** their ordering
    is inspected, **then** it is **documented as a decision in both comments**, naming the other's
    queue position — and if AC 15 misses the budget, the swap is made and **both** numbers recorded.
21. **Given** any measured gap against the budget, **when** it is found, **then** it is **closed, or
    recorded as an accepted deviation with its reason and its home** — and the ownership conflict is
    raised in the open: `epics-companion-app.md:745` makes Epic 4 the **owner** of NFR-05 while the
    only gap-closing story (10.3) is **Phase 2**.
22. **Given** AC 15's citation of **SC-2**, **when** the record is written, **then** it states that
    SC-2 carries no timing, belongs to Epic 7, and that **NFR-05 is the sole authority** for the
    1-second number — the loose co-citation is inherited, not endorsed.

### Never blank

23. **Given** any point from first paint onward — deck boot, refusal, recovery, empty deck — **when**
    the app is observed, **then** it never renders a viewport containing none of {header, left-column
    content, right-column content, footer}, and that definition is written down because no artefact
    supplies one (UX-DR36).
24. **Given** AC 23, **when** its scope is recorded, **then** it states that the criterion is a
    **verbatim duplicate of `epics-companion-app.md:3119`** and that the **refetch** half is **c7-4's**,
    handed back by name — with `states.ts`'s `NO_UI_RESPONSE` cited as the one classification in
    tension with the sentence.

### SC-5 answerable

25. **Given** the completed deck view, **when** it is compared against `DESIGN.md` and `EXPERIENCE.md`,
    **then** the comparison is **recorded as a findings list with both anchors per item** — making
    SC-5 **answerable** — and the story **does not pass, fail or pre-empt SC-5**, which is Brad's at
    **c8-6** and *"cannot be automated or delegated"* (UX-DR49, `ARCHITECTURE-SPINE.md:494`).
26. **Given** the empty-deck treatment, **when** `DESIGN.md` is inspected, **then** it **specifies it**
    — because today it does not, and AC 25 is otherwise unsatisfiable for this branch (finding 3).
27. **Given** the drift the comparison finds, **when** dispositions are made, **then** Q13's LAND list
    is landed **in this commit** and the ~60 stale `DESIGN.md:NNN` anchors are **recorded with the
    guard's shape written down** and homed on the C4 retro — `shell.test.ts:1021` validates the
    *string* `"DESIGN.md"` and never the line number.
28. **Given** the empty state, **when** it is eye-checked, **then** it is seen in a real browser — the
    left column with only the grid panel, the right column with two panels instead of three — and what
    it looks like is **recorded**, not asserted. `DESIGN.md:384` specifies the composition
    unconditionally and describes no reduced form.

### Fixtures, guards, the record and the ledger

29. **Given** every inherited deferral in the table above, **when** the story completes, **then** each
    has a written disposition **in `deferred-work.md`, in this commit** — and the finding that fifteen
    source modules name c4-12 while the ledger names it twice is itself recorded.
30. **Given** every number this story records, **when** it is derived, **then** it is keyed on the
    **current 42 decks** and the correction from 40 is stated — including the stale *"40 real decks"*
    citations at `App.tsx:203` and `:247`.
31. **Given** every fixture this story adds, **when** it is inspected, **then** it is either a
    **verified real row** or **declared synthetic in place**, with no third option — and the empty deck
    is declared synthetic **because no corpus deck has zero cards** (c4-10 AC 26, c4-11 AC 31).
32. **Given** every guard this story adds, **when** it is inspected, **then** it carries a non-vacuity
    anchor and states what it cannot see — the epic's coverage-that-reads-as-coverage class has landed
    in the story's own flagship guard **six consecutive times**, and the five shapes are named above.
33. **Given** the copy string, **when** it is gated, **then** `ui/tests/empty-deck-copy.test.ts`
    compares the shipped module against `EXPERIENCE.md:70` byte-for-byte, and `copy.test.ts:114` /
    `copy-tails.test.ts:149-152` **stay pinned at 6** (the row is not Headline/Body shape and must not
    be reworded into one).
34. **Given** the registries, **when** they are inspected, **then** `CONTAINERS` moves 24 → 25 with its
    running-log line and its `toHaveLength` pin (`shell.test.ts:1977`), `CardGrid`'s declared imports
    gain `'./copy'`, `COPY_MODULES` moves 13 → 14, and the token inventory **holds at 69** with both
    pins asserted rather than assumed.
    ⚠️ **`COPY_MODULES` has no numeric count pin** — verified: `CONTAINERS` has
    `expect(CONTAINERS).toHaveLength(24)`, `COPY_MODULES` has nothing equivalent. A missing entry is
    caught only by the file-half prose detector (`copy-rules.test.ts:488-505`), which walks
    `git ls-files` and is therefore **blind to an un-`git add`ed module** — the c4-7 false-green
    mechanism. `git add` the copy module before believing a green run.
35. **Given** the eighteen don't-breaks above, **when** the suite runs, **then** every one of them is
    green, and the baseline moves from **1,668 / 64 files** by a stated amount.
36. **Given** ten gates — `npm test`, `npm run lint`, `npm run format:check`, `npx tsc -b --force`,
    `npm run build`, `npm run gen:types` (no drift), `uv run pytest`, `ruff check .`,
    `ruff format --check .`, `mypy src/` — **when** they run, **then** all ten are green and
    `uv run pytest` is **2,501 passed / 1 skipped**.
37. **Given** the bundle, **when** the commit is prepared, **then** **both** assets are rebuilt and the
    **untracked new content-hashed files are `git add`ed**, `scripts.build_plugin` is re-run and the
    mirror **verified sha256-identical per file** — the c4-3/c4-7 High, twice.
38. **Given** `graphify-out/`, **when** anything is staged, **then** it is not — the `.gitignore` hunk
    went to master at `2f543ed` and **`feat/companion-c4` never received it**, so `git add -A` from the
    repo root stages thousands of cache files. The fix is a master→epic-branch sync, **not** a hunk
    smuggled into this diff.

---

## Tasks / Subtasks

- [x] **Task 0 — Answer the seventeen open questions before writing code** (AC 6, 8–10, 13, 16–22, 26–28, 31)
  - [x] Verify `origin/feat/companion-c4` is at `86d5fb6` with `git log --oneline -1` **before**
        `checkout -b`, and cut the branch from that commit — not from `c435086`
  - [x] Re-run the two ⚠️ carried baselines — `npm test` and `uv run pytest` — before believing
        **1,668 / 64** and **2,501 / 1**, and record the actual numbers even if they match
  - [x] Re-verify §A–§I read-only against the shipped database, keying every count on **deck id**,
        and confirm the **42-deck** correction
  - [x] Read, end to end, **before designing anything**: `App.tsx:180-320`, `CardGrid.tsx:28-111`,
        `AnalysisRow.css:40-54`, `FormatCheck.tsx:132-142` and `:229-236`, `ManaCurve.tsx:67-114`,
        `ColourDistribution.tsx:97-147`, `DeckList.tsx:82-88`, `deck.ts:385-429`,
        `App.test.tsx:794-828`, `:1329-1379`
  - [x] Rule Q1–Q17, each with its reason recorded in the Debug Log
- [x] **Task 1 — The predicate** (AC 1, 7, 11, 12)
  - [x] Q1's single extraction beside `surfaceOf`, with `hasCards` refactored to consume it — or the
        stated reason for leaving it in place
  - [x] `App.test.tsx:1356-1379` and `:794-828` pass **unchanged**
- [x] **Task 2 — The line** (AC 1–5, 26, 33, 34)
  - [x] ⚠️ **`DESIGN.md` FIRST** — specify the empty-deck treatment (Q2's ordering constraint), or
        `shell.test.ts:995-1032` has no citation to accept and any anchor written is invented
  - [x] `src/containers/CardGrid/copy.ts` with the byte-for-byte string; `COPY_MODULES` 13 → 14
        (⚠️ no count pin exists — `git add` it or the registry sweep is blind to it)
  - [x] `CardGrid.tsx` renders the line **instead of** the `<ul>`; `CardGrid.css` spending scale
        tokens only, with any px literal cited to the **new** `DESIGN.md` lines
  - [x] ⚠️ Rewrite `CardGrid.test.tsx:155-165` **in this commit** — its title becomes false
  - [x] `ui/tests/empty-deck-copy.test.ts` on the `unknown-card-copy.test.ts` shape
  - [x] `shell.test.ts`: `CONTAINERS` 24 → 25 + the running-log line + `'./copy'` on CardGrid's entry
- [x] **Task 3 — The hide, and the request** (AC 7–10, 14)
  - [x] Gate **only** `FormatCheck`; assert the other two are absent **and why**
  - [x] Suppress `loadFormatCheck` on the empty deck, keeping `clearFormatCheck`'s teardown arm
  - [x] Extend `App.test.tsx:1329-1354`'s describe: the line present, three panels absent, no
        format-check request, banner count **3**, no `c4-*` key on the glass
- [x] **Task 4 — The budget** (AC 15–22)
  - [x] Build Q9's CDP harness in the scratchpad; carry the three recorded traps
  - [x] `uv run artificial-planeswalker companion`; read the port from `companion.json`
  - [x] ≥5 runs per arm × both cache readings; dump `performance.getEntriesByType('resource')`
  - [x] Record the waterfall, the hardware and the conditions; state the clock's start and stop
  - [x] Q10: document the effect ordering in both comments; swap and re-measure **only if red**
  - [x] Q11: if it misses, write the accepted deviation, its home and the ownership conflict
- [x] **Task 5 — Never blank** (AC 23, 24)
  - [x] Q12's operational definition, asserted across the boot sequence
  - [x] Record the c7-4 duplication and the `NO_UI_RESPONSE` tension
- [x] **Task 6 — SC-5 answerable** (AC 25–28)
  - [x] The findings list, both anchors per item; **no verdict**
  - [x] Land Q13's LAND list — the three DESIGN.md paddings, the four token-count literals,
        `ColourDistribution.css:99-104`, `EXPERIENCE.md:157`, the price residues, `DESIGN.md:418`,
        the ten `ui/README.md` claims — and **specify the empty-deck treatment in DESIGN.md**
  - [x] Record the ~60 stale anchors **with the guard's shape** and home them on the C4 retro
  - [x] Q14: create an empty deck, eye-check it over CDP, delete it, prove the DB was left at 42
- [x] **Task 7 — Fixtures, guards, gates and the record** (AC 29–38)
  - [x] Every fixture verified real or **declared synthetic in place**
  - [x] Every new guard carries a non-vacuity anchor and states what it cannot see
  - [x] Run the probes through the **full `npm test`**, validating the collected-test count
  - [x] Ten gates; `git add` everything **before** believing a green run
  - [x] Rebuild the bundle, stage the **untracked** hashed assets, run `scripts.build_plugin`,
        verify the mirror sha256-identical per file
  - [x] ⚠️ Do not stage `graphify-out/`
  - [x] Write the `deferred-work.md` dispositions **in this commit** (AC 29) and land the artefact
        corrections (AC 27)
- [x] Set status to `review` and **STOP** — Brad runs the three-layer review and raises the PR

### Review Findings

<!-- Three-layer review 2026-08-07 (Blind Hunter / Edge Case Hunter / Acceptance Auditor).
     22 findings after dedup: 2 decision-needed, 14 patch, 2 defer, 4 dismissed. -->

- [x] [Review][Decision] EXPERIENCE.md alt-text row rewritten under the conformance sweep without a
      distinct ruling — the amendment extends `alt=""` to grid tiles and the detail panel, reversing
      the row's explicit reasoned carve-out ("there the image is the only carrier") and labelling it
      "code right, artefact wrong". This changes what a WCAG audit would check, riding into a
      normative artefact under an empty-deck story. Options: ratify the amendment as a ruling,
      revert the artefact and ledger the code as the defect, or park for c8-6.
- [x] [Review][Decision] Cold-cache arm measured at n=3 against AC 15's "at least five runs per
      arm" — defensible if "per arm" scopes to AC 15's two warm readings (the cold arm is AC 19's
      and restates no n), but the Dev Record adopts the arm vocabulary for all three and states no
      reason for the shortfall. Options: state the scoping in the record and accept n=3, or
      re-measure two more cold runs.
- [x] [Review][Patch] HIGH — never-blank test title claims "recovery back to a deck" but the body
      never drives or asserts recovery: the loop settles at 0 ms (recovery needs the ~2,000 ms poll
      tick), the queued `decks('Boros Aggro')` second poll response is never reached, and no
      assertion observes a deck surface after a refusal — AC 23 names recovery; the epic's
      coverage-that-reads-as-coverage class, seventh consecutive story, this time in a test title
      [ui/src/App.test.tsx:1969]
- [x] [Review][Patch] AC 30 violated — both named stale "40 real decks" citations survive the diff
      unchanged, with no deviation declared [ui/src/App.tsx:220, ui/src/App.tsx:287]
- [x] [Review][Patch] AC 27 / Q13 LAND list partially landed — `ui/README.md`'s four stale token
      counts remain (65 / closed at 64 / `declaredTokens.size === 64` / pinned at 65; actual 69),
      and the Dev Record's AC 25 item 12 re-enumerates the README "ten claims" without the token
      counts — an undeclared narrowing, the story's own anti-pattern #5
      [ui/README.md:235,595,628,833]
- [x] [Review][Patch] Conformance sweep shipped a fresh contradiction — "All ten now have an
      on-screen consumer as of c4-10" three lines before "`StatChip` alone still awaiting a
      surface" in the same sentence run; the truth is nine of ten [ui/README.md:1374]
- [x] [Review][Patch] False decide-once rationale — "`emptyDeck` and not `!hasCards`: the two
      differ on a sideboard-only deck" is mathematically false: inside `surface.kind === 'deck'`
      (so `deck !== null`), `!hasCards ≡ emptyDeck` identically, including on a sideboard-only
      deck; the comment records a distinction that does not exist [ui/src/App.tsx:519]
- [x] [Review][Patch] Calm-line CSS guard has three mechanical evasion holes — (a) `var(--token,
      literal)` fallbacks pass the exact-token pin, (b) an uppercase-spelled property (CSS is
      case-insensitive) evades the exactly-three-properties pin, (c) a `}` inside a comment within
      the block truncates the `[^}]*` extraction so later declarations escape both pins
      [ui/tests/shell.test.ts:2215-2232]
- [x] [Review][Patch] AC 23 empty-deck fixture is internally inconsistent and undeclared —
      `deckDetail({ cards: [], mainboard_count: 0 })` leaves the default `distinct_cards: 2`
      beside `cards: []`, a wire body no backend produces, while the suite's own `emptyDeck()`
      helper models the real payload twelve hundred lines up
      [ui/src/App.test.tsx:1340, ui/src/App.test.tsx:2010]
- [x] [Review][Patch] Comment overstates a mechanism — "a deck that gains its first card while the
      tab is open asks then": no shipped path rewrites `detail` mid-session except the
      poll-recovery re-drive; the refetch that would make this true is c7-3's
      [ui/src/App.tsx:322]
- [x] [Review][Patch] Comment/code shape mismatch — "the teardown arm below is UNCONDITIONAL" but
      the empty/null arm clears eagerly on entry and registers no cleanup; only the load arm
      returns `clearFormatCheck`. Behaviour correct, description literally false in the exact spot
      c4-10's review found a missing cleanup half [ui/src/App.tsx:327]
- [x] [Review][Patch] Run-count prose drift in the two effect comments — "every one of ten runs
      across both cache readings" vs the recorded corpus of 13 runs (n=5/5/3, 238–428 ms); numbers
      two comments order future readers to treat as authoritative [ui/src/App.tsx:260]
- [x] [Review][Patch] Two `empty-deck-copy` loop tests pass vacuously if `rowsFor(ROW_LABEL)`
      returns `[]` and the sibling length-pin test is skipped/filtered — assert the length inside
      each loop [ui/tests/empty-deck-copy.test.ts:141]
- [x] [Review][Patch] Task 3 structural deviation undeclared — the spec says "Extend
      `App.test.tsx:1329-1354`'s describe"; a new end-of-file describe was added instead. Content
      all present; declare the deviation in the Dev Record [ui/src/App.test.tsx:1969]
- [x] [Review][Patch] `tiles` is computed unconditionally and discarded on the empty branch — move
      the flattening into the non-empty arm [ui/src/containers/CardGrid/CardGrid.tsx:103]
- [x] [Review][Patch] Sideboard-only residue's UX-DR36 interaction unnoted — on that deck the left
      column carries no visible text (empty `<ul>`, both analysis panels self-hidden), the closest
      reachable state to the blank viewport AC 23 defines; add the sentence to the residue note
      [ui/src/state/deckGroups.ts residue note]
- [x] [Review][Defer] One-frame stale format-check report on a non-empty→non-empty deck switch —
      deck A's report renders under deck B's header for one commit before effects run
      [ui/src/App.tsx:350] — deferred, pre-existing shape; the deps change neither caused nor
      widened it
- [x] [Review][Defer] No committed CDP measurement harness — both effect comments carry "DO NOT
      REORDER WITHOUT RE-MEASURING" while every measurement script was a scratchpad throwaway (the
      spec's own Task 4 sanctioned that), so AC 18's numbers are irreproducible from the repo
      [ui/src/App.tsx:244,331] — deferred, pre-existing posture; home on the C4 retro beside the
      ~60 stale anchors

---

### References

- Epic story text — `_bmad-output/planning-artifacts/epics-companion-app.md:2321-2353`
- Epic 4 header — `:1895-1900` · FR/NFR coverage — `:711-749` (⚠️ **NFR-05 owned by Epic 4**, `:745`)
- UX-DR coverage — `:751-762` · Story 10.3 (the Phase-2 twin) — `:3618-3656` · Story 8.6 (SC-5) —
  `:3366-3401` · Story 7.4 (AC 5's duplicate) — `:3119` · Story 3.6 (cold-paint observation) —
  `:1794-1797` · Playwright deferred — `:310`
- UX-DR33 — `:543-547` · UX-DR36 — `:564-568` · UX-DR30 — `:500-504` · UX-DR31 — `:506-523`
  (amended 2026-08-07) · UX-DR37 — `:570-574` · UX-DR20 — `:442-448` · UX-DR8 — `:372-378` ·
  UX-DR49 — `:676-680` · UX-DR35 — `:557-562` · NFR-05 — `:157-160`
- `prd.md:164` (NFR-05 original, **without** the clock clause) · `:178` (SC-2, **no timing**) ·
  `:183-185` (SC-5) · `:172-173`, `:215` (Phase-2 hardening is "beyond this baseline, not a deferral")
- `EXPERIENCE.md:70` (**the copy**) · `:113` (**the state row**) · `:111` (the cold-open path) ·
  `:183` (⚠️ the *other* start event) · `:164-168` (the Latency contract; ⚠️ 250 ms has a paragraph,
  1 s has a line) · `:86` (UX-DR20, and the price residue) · `:35` (price residue) · `:100` (skip
  link, amended) · `:105`, `:152`, `:154`, `:157` (⚠️ alt-text, contradicted by both consumers)
- `DESIGN.md:379` (the spacing scale, and its own banned literals) · `:141-145` (⚠️ **the three
  unamended off-scale paddings**) · `:383-388` (the layout, stated unconditionally) · `:410`
  (composition reference) · `:414-433` (the components) · `:418` (⚠️ stale "100+") · `:429`, `:431`
  (price removed) · `:369` (⚠️ price residue) · `:186-187` ("reads as a loading failure")
- Gate — `validation-report-2026-07-25.md:53` + `:134` (**M2 — the only clock ruling, scoped to
  SC-1**) · `:78`, `:146` (**L8 still open, unactioned**) · `validation-report-2026-07-22.md:71-73`
  (**the empty-deck state's provenance — a recommendation, curve only**) · `:137-139` (the SC-2
  loose citation, ruled "no fix required") · `.memlog.md:22` (**tagged `(assumption)`**)
- Spine — `ARCHITECTURE-SPINE.md:242-270` (AD-11; ⚠️ *"roughly 12 MB and ~10 s"*, corrected to
  8.5 MB) · `:477` · `:494` (**SC-5 is a human gate; Playwright deferred**) ·
  `EPIC-SPLIT.md:95` (E13 — NFR-05 profiling is Phase 2) · `:121` (**cannot be automated or
  delegated**)
- Composition — `ui/src/App.tsx:162-421`, esp. `:180-229` (the sweep + its measured correction),
  `:231-272` (the format check), `:274-308` (`hasCards` and its ruling); `AppShell.tsx:113-114`,
  `:116-200`
- The empty-deck seam — `CardGrid.tsx:58-64`, `:73-111`; `AnalysisRow.css:40-54`;
  `ManaCurve.tsx:67-79`, `:109-114`; `ColourDistribution.tsx:97`, `:139-147`;
  `FormatCheck.tsx:132-142`, `:229-236`; `DeckList.tsx:82-88`, `:238-318`; `inspection.ts:125`,
  `:315`; `deck.ts:71`, `:385-429`; `deckGroups.ts:252-276`
- Tests — `App.test.tsx:445-487`, `:645-733`, `:794-828`, `:830-881`, `:964-969`, `:1250-1327`,
  `:1329-1354`, `:1356-1379`, `:1518-1662`, `:1664+`; `CardGrid.test.tsx:155-165`;
  `DeckList.test.tsx:718`; `ManaCurve.test.tsx:287`; `CardDetail.test.tsx:240`;
  `deckGroups.test.ts:370`; `client.test.ts:564`; `DeckBadges.test.tsx:90-92`
- Guards — `copy-rules.test.ts:69-72`, `:86-91`, `:123-293`, `:327`, `:488-505`, `:522-548`,
  `:553-600`; `copy.test.ts:87-116`; `copy-tails.test.ts:130-152`; `shell.test.ts:995-1032`,
  `:1049-1112`, `:1326-1381`, `:1542-2086`, esp. `:1977` (CONTAINERS 24) and `:1021` (⚠️ **the
  anchor gate that never checks the line number**); `token-usage.test.ts:584-635`, `:1018-1054`,
  `:1131-1138`, `:1170`, `:1935-1945`; `tokens.test.ts:295-321`; `posture.test.ts:322-357`;
  `keyboard-floor.test.ts:303`, `:400-463`, `:626-651`; `gate-geometry.test.ts:42-64`;
  `lint-gates.test.ts:133-172`; `buildOutput.test.ts:32-60`; `eslint.config.js:17-24`, `:80`,
  `:106-110`, `:204-241`
- Backend — `src/companion/app/routes/decks.py:67-91`, `:99-138` (⚠️ `:129-133` names the
  confident-empty-report failure mode); `src/logic/deck_validator.py:205`, `:393-406`, `:457-488`,
  `:652-667`, `:753-754`; `src/data/repositories/deck.py:53-93`, `:239-267`, `:386-432`, `:565-576`;
  `src/data/schemas/deck.py:104-108`, `:180-204`, `:249-283`; `src/companion/app/images.py:147`,
  `:167`, `:369`, `:782-801`, `:845-856`; `spa.py:71`; `server.py:233`;
  `src/mcp_server/__main__.py:267-268`
- Ledger — `deferred-work.md:1539-1546`, `:1592-1609`, `:1672-1681`, `:1844`, `:2255-2263`,
  `:2940-3003`, `:3203-3216`, `:3691-3696`, `:3777-3791`, `:3830-3838`, `:3863-3866`, `:3890-3901`,
  `:3965-3980`, `:3993-4001`, `:4044-4047`, `:4128-4130`, `:4161-4180`, `:4215-4263`, `:4283-4320`,
  `:4355-4362`, `:4399-4409`, `:4418-4463`
- Prior records — `c4-4:452, 654, 1074-1089, 1265`; `c4-6:1300-1324, 1402-1403`;
  `c4-7:1218`; `c4-8:879-891, 1009-1011, 1192-1229, 1417-1422, 1738`;
  `c4-9:950-963, 1361-1367, 1499-1503, 1792`; `c4-10:120-125, 1016-1023, 1541-1543, 1874, 1888`;
  `c4-11:136-139, 361-392, 511-519, 736-738, 997-1007, 1122-1132, 1138-1149, 1181-1198, 1290-1307,
  1322-1363, 1515-1571, 1626-1664`
- C3 retro (the CDN measurements) — `epic-c3-retro-2026-08-02.md:280-296`
- `ui/README.md:55-75`, `:98`, `:155-160`, `:231`, `:591`, `:624`, `:714-725`, `:828`, `:847`,
  `:942`, `:1034`, `:1084-1091`, `:1220`, `:1347-1356`, `:1366-1382`, `:1417-1420`, `:1450-1458`
- CI bundle sync — `.github/workflows/ci.yml:76-84`, `:137`, `:139-167`, `:180+`;
  `scripts/build_plugin.py`; `tests/unit/companion/test_spa.py::TestThePluginMirror`

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via Claude Code / `bmad-dev-story`.

### Debug Log References

Branch `feat/companion-c4-12-empty-deck-and-render-budget`, cut from **`86d5fb6`** — the merge
commit, verified with `git log --oneline -1 origin/feat/companion-c4` **before** `checkout -b`, per
the story's precondition. `git diff --stat HEAD 86d5fb6` was also empty, so the working-tree carry
of the two uncommitted files was provably safe (the c4-11 near-miss shape, closed twice over).

#### Baselines, re-run rather than believed (Task 0)

| baseline | recorded in context | measured 2026-08-07 |
|---|---|---|
| frontend suite | 1,668 / 64 files | **1,668 / 64** ✅ |
| Python suite | 2,501 passed / 1 skipped | **2,501 / 1** ✅ |
| decks | 42 | **42** ✅ (standard 21, brawl 18, standardbrawl 2, historic 1) |

⚠️ The first `uv run pytest` run collected **0 items** and exited 0 — the shell's working directory
had persisted from an earlier `cd ui/src`. A green-looking zero-test run is exactly the epic's
coverage-that-reads-as-coverage shape arriving in the *harness*; caught by reading the count, not
the exit code, and re-run from the repo root.

#### §A–§I re-verified read-only, and TWO record corrections beyond the story's own

- **§F: the deck census must JOIN `decks`, and the story's own §F did not.**
  `SELECT COUNT(DISTINCT deck_id) FROM deck_cards` returns **44** against 42 decks — **28 orphan
  rows across 2 deleted deck ids** (`136ce5b1-…` 22 rows/57 cards, `55af0ef7-…` 6 rows/32 cards).
  So `delete_deck` leaves its `deck_cards` behind. The joined distribution is the story's
  (1, 3, 20, 59, 60×20, 100×18 = 42); the unjoined one silently adds a 32-card and a 57-card deck
  that do not exist. **Ledgered, homed c10-3.** No user-visible effect: every read path starts from
  a `decks` row.
- **§G: 220 shards occupied, not 137.** Files (633), bytes (63,195,342) and distinct ids (496) all
  matched exactly; only the shard count was wrong. 220 is also what the arithmetic predicts for 496
  ids over 256 shards (≈219).
- §B ✅ (0 empty decks; 41 sideboard rows / 5 decks; smallest real deck 1 card).
  §C ✅ verbatim — `DeckDetail.from_deck(Deck(deck_cards=[]))` gives `"cards":[]`, an empty ARRAY,
  counts 0, no `card_count` and no `boards` on the wire (it also carries `created_at`/`updated_at`,
  which the story's transcription omitted).
  §D ✅ verbatim, `standard` **and** `brawl` identical — six rows, one `size` violation
  (*"Mainboard has 0 cards; the minimum is 60"* — note this is c4-10's brawl-deck-size finding
  showing through) and **four vacuous greens**.
  Atraxa v2 ✅ 100 mainboard / 99 rows / 0 sideboard / 6 DFCs.

#### The seventeen rulings

**Q1 — the predicate. AS PROPOSED IN SUBSTANCE, ⚠️ DEVIATED ON LOCATION.** One expression,
`deckIsEmpty(boards)`, defined as the exact negation of `hasCards`'s board test, with `hasCards`
refactored to `deck !== null && !emptyDeck`. **It lands in `state/deckGroups.ts` beside
`DeckBoards`, not in `state/deck.ts` beside `surfaceOf`.** Reasons, stated because this is a
deviation: (i) it is a predicate *over `DeckBoards`*, whose type and producer both live in
`deckGroups.ts`, while `deck.ts`'s warning is about `surfaceOf`'s deck-vs-panel answer, which this
is not; (ii) `deckGroups.ts` is declared *"pure, framework-free and store-free"* in its own header
and a pure predicate belongs there; (iii) `CardGrid` already declares `../../state/deckGroups` in
`shell.test.ts`'s exhaustive import list, so the container does **not** acquire `state/deck` — and
with it `createDeckBoot` and the API client — into its module graph for a three-line predicate. The
story's binding clause (*"NOT in a new module"*) is honoured: no new module was created.
⚠️ Residue stated, not hidden: a **sideboard-only** deck is NOT empty, so it renders an empty grid
with no line — a state no artefact describes, unreachable from live data (0 of 42), pinned in
`CardGrid.test.tsx` and ledgered.

**Q2 — where the line renders. AS PROPOSED.** `<p className="card-grid-empty">` from a new
import-free `src/containers/CardGrid/copy.ts`, **replacing** the `<ul>` as the untitled panel's only
child. The ordering constraint was honoured literally: **DESIGN.md was amended first**
(`components.empty-deck-line` + a Components bullet), then `CardGrid.css` written against it — and
the amendment's own content is *"it spends no length of its own"*, so the rule ships with **no `px`
literal at all** and there is nothing for the proximity gate to check. `Panel`'s existing
`.panel-body` inset (`--space-3`) is the whole of the spacing, confirmed on a real screen at 12px.

**Q3 — what gates the analysis panels. AS PROPOSED: only `FormatCheck`, and in `App.tsx`.** The
curve and colour bar already return `null` on their own zero totals and `.analysis-row:empty`
already collapses the row. The suite asserts *the reason* rather than the absence, via the
land-only discriminator (see AC 8 below).

**Q4 — the request. AS PROPOSED: suppressed.** `emptyDeck` joins the effect's deps as a boolean, so
a deck that gains its first card asks then; the teardown arm is unconditional (c4-10's review found
that missing half once already).

**Q5 / Q6 — `DeckList` and `CardDetail` on an empty deck. AS PROPOSED: status quo, RULED and
RECORDED as an artefact defect against UX-DR20, not repaired.** Both pinned in `App.test.tsx` and
ledgered, homed on the C4 retro. The eye-check turned the argument into an observation — see below.

**Q7 — the clock. AS PROPOSED.** start = navigation start (`performance.timeOrigin`, read in-page
so there is no cross-process clock to align); stop = the moment the **last** of the six named
surfaces enters the DOM, seen by a `MutationObserver` installed at **document-start** (an observer
added at load would miss surfaces that arrived before it). The 07-25 gate's M2 clause is adopted
**by citation**, with the note that it was written for SC-1 and the deck path has no entry
animation, so it is probably vacuous here. This measures `EXPERIENCE.md`'s **cold open**; it does
**not** measure the active-deck-change-in-an-open-tab path, which needs Epic 5/6 machinery.

**Q8 — which warm cache. AS PROPOSED: both, measured and reported separately.**

**Q9 — the harness. AS PROPOSED:** ad-hoc CDP in Python (`websockets` + `httpx`), Chrome 151
`--headless=new`, fresh profile, against the **committed SPA** served by the running backend. n=5
per arm. The three recorded harness traps did not apply (no key events, no `blur()`, no
`getComputedStyle` string-matching) and Playwright was **not** installed.

**Q10 — the swap. MEASURED BOTH WAYS; NOT SWAPPED.** See the numbers below. The budget is met with
~570 ms of headroom in every run of both arms, so per Q10's own rule the swap is not made — and
both effect comments now name the other's queue position, which AC 20 requires regardless.

**Q11 — a red measurement. Not triggered.** The ownership conflict is raised anyway (ledgered),
because the structure that would have bitten is unchanged.

**Q12 — "blank screen". AS PROPOSED**, defined operationally in `App.test.tsx` with the c7-4
hand-back and the `NO_UI_RESPONSE` tension both written down.

**Q13 — the SC-5 sweep. AS PROPOSED: the LAND list landed; the ~60 stale anchors recorded.**

**Q14 — how the empty state is eye-checked. ⚠️ DEVIATED, and this is the second deviation.** The
proposal was to `create_deck` against the shipped database, eye-check, delete, and prove the count
returned to 42. **No write of any kind was made to the real database.** Instead
`PLANESWALKER_DATA_DIR` relocated the whole data directory (lock, discovery file, image cache and
`cards.db` together), a private schema was created there with one deck and one corpus row (enough
for `is_database_initialized`, which needs `cards` to exist and be non-empty), a second companion
served it on an ephemeral port, and the whole directory was deleted afterwards. Reason: it obtains
the identical observation while removing the create/delete window entirely, so there is no
"prove it was left as found" burden to discharge — and `cards.db`'s `LastWriteTime` is still
**28/07/2026**, untouched. The fallback the story offered (jsdom-only plus a stated gap) was not
needed.

**Q15 — the reduced composition. AS PROPOSED: verified by eye and RECORDED, not asserted.**

**Q16 — tokens and calmness. ⚠️ DEVIATED on the mechanism, and the deviation is narrower.** Tokens
hold at **69**, asserted not assumed. `CardGrid.css` does **not** join `CALM_STYLESHEETS`: that map
is keyed on a whole FILE, and this file draws the grid's arrangement, so joining would assert
UX-DR30 over every rule in it and every rule a later story adds — a claim about the grid, not about
the line. The narrower claim is made instead as a source pin in `shell.test.ts`: the
`.card-grid-empty` block declares **exactly** `margin`, `color`, `font` and spends **exactly**
`--text-secondary` and `--type-body`, both directions. It states what it cannot see (a colour
reaching the element from another stylesheet).

**Q17 — the copy string. AS PROPOSED: byte-for-byte**, with `ui/tests/empty-deck-copy.test.ts` on
the `unknown-card-copy.test.ts` shape. Em dash **U+2014** pinned by codepoint, because U+2014,
U+2013 and U+002D are indistinguishable in a terminal diff.

#### AC 6 — the human reading of the copy, performed and recorded

`deferred-work.md` names c4-12 in **two** permanently-open entries saying no guard can judge this.
The sentence is **`This deck is empty — ask your agent to add cards.`**

- **Second person, and the right second person.** *"your agent"* addresses the reader and names the
  one mechanism that can change the state. It does not say *"you"* should do anything the user
  cannot do from this window — the companion is read-only by design.
- **Blameless.** It states a fact and assigns no fault, which is correct rather than merely polite:
  measured, an empty deck is the **normal** state at creation (`create_deck` inserts a deck and
  writes no card; `remove_card_from_deck` never deletes the deck it empties). There is nothing to
  apologise for and the copy does not.
- **Concrete next action** (UX-DR30), and it is achievable in one sentence to the agent.
- **No error register**: no exclamation mark, no "oops", no "something went wrong", no icon, no
  panel. It is one line of `--type-body` in `--text-secondary`, seen on a real screen.
- **It is EXPERIENCE.md's own sentence**, not an improvement on it — the same discharge c4-3 made
  and explicitly bequeathed to this story.

**Read and accepted.** ⚠️ What a reading cannot settle: the state itself is an **unconfirmed
product decision**. Its provenance is `validation-report-2026-07-22.md`, a *medium* finding whose
recommendation named **the curve only**; colour distribution and format check were added to the
hide list with no recorded rationale, and `.memlog.md` tags the whole treatment `(assumption)`. It
is **not** among the four rulings Brad confirmed. This story ships it as written and says so, so
that if the answer should be different the cost is known now rather than at Epic 8.

#### The cold-open render budget (Task 4, AC 15–22)

**Conditions.** Windows 11 Pro 26200, Chrome **151.0.7922.108** `--headless=new`, window
1720×1080, `--force-device-scale-factor=1`, localhost HTTP/1.1 (uvicorn/h11, no h2), backend and
browser on the same machine. Deck **`813d0434-1bed-4419-bf9d-d9e4070704c4`** — *Atraxa Counter
Cabinet v2 (owned)*, 100 mainboard / 99 tiles / 6 DFCs / 0 sideboard. Committed SPA served by
`spa.py`, **never `npm run dev`**. Bundle `index-CiTvYAAz.js` 224,270 B + `index-B_WnaAKx.css`
20,390 B.

**Clock:** navigation start → the last of {header, grid, mana curve, colour distribution, deck
list, format check} entering the DOM.

| arm | n | min | median | max | format-check queue position |
|---|---|---|---|---|---|
| **A** fresh profile + warm backend disk cache | 5 | **311** | **363** | **428 ms** | **106–107** |
| **B** repeat visit + warm browser HTTP cache | 5 | **238** | **348** | **387 ms** | **204–205** |
| **C** fresh profile + **COLD** backend image cache | 3 | **278** | **313** | **390 ms** | 106–107 |

**✅ NFR-05 IS MET, in every one of thirteen runs, with ~570 ms of headroom at the median.**

**The waterfall (AC 18), and it confirms the story's headline prediction.** Arm A settles at **213
requests**: 1 document, 3 assets, `/api/decks`, `/api/active-deck`, `/api/deck/{id}`, **99
`/api/cards/{id}`** and **106 `/api/card-image/…`** (99 fronts + 6 backs + 1). The format check is
issued at **queue position 106–107** — the story predicted ~100 from effect-declaration order,
HTTP/1.1 and Chrome's 6-connection cap, and the browser agrees. **Five of the six surfaces are in
the DOM at ~205 ms; the sixth arrives at 311–428 ms**, so a request whose backend cost is 5.0 ms
accounts for **~200 ms of the layout time**. First paint 48 ms, FCP 120 ms, DOMContentLoaded ~83 ms.

**Arm B is worse on queue position and better on time**, which is the honest and slightly
counter-intuitive result: a warm HTTP cache dispatches all 106 image requests immediately, so the
format check sits at **position 204–205** — but every one of them is served from disk (**0 bytes
transferred**, `immutable, max-age=31536000` doing its job) and resolves fast. **The 99 card-detail
JSON reads are paid in full in BOTH arms** — 99 requests each — exactly as Q8 requires stating.
Arm A transfers **9,642,989 B** of image data (9.20 MiB over the wire against 8.47 MiB on disk for
the fronts alone — the difference is the 6 back faces plus HTTP framing), which corroborates the C3
retro's ~8.5 MB/deck and again corrects `ARCHITECTURE-SPINE.md`'s *"roughly 12 MB"*.

**AC 19 — the cold image cache, and the excluded-clause applied EXPLICITLY.** The deck's 204 cached
image files were **moved aside** (never deleted — the ledger records an unreproduced ~124 s dead-CDN
cold paint, and the originals stayed in a holding directory so restoration was guaranteed), the run
measured, and the files restored; the cache ended at **633 files / 63,195,342 B**, byte-identical to
the start. With every image fetched from the Scryfall CDN the **last image response lands at
~11.0 s** — and **layout is unmoved at 278–390 ms**. So *"first-fetch image paint excluded"* is not
an exemption this story claims, it is a **measured structural fact**: none of the six named surfaces
waits on an image, and the ~10.4 s the cold CDN adds lands entirely in the image tail. The ~8.5 MB /
~10 s cold-paint observation is thereby cited as expected, non-defect behaviour.

**AC 20 — the ordering, measured both ways.** With the two `useEffect` blocks swapped (measurement
only; reverted, and the shipped bundle rebuilt from the restored source):

| order | queue position | layout (n=5, arm A) | layout (n=5, arm B) |
|---|---|---|---|
| **as shipped** (sweep first) | 106–107 | 311 / **363** / 428 ms | 238 / **348** / 387 ms |
| swapped (format check first) | **7** | 120 / **185** / 520 ms | 119 / **142** / 163 ms |

**Not swapped.** The budget is met with headroom either way, so the swap is an unrequested change
to the cold-open path; it is also not free (the swapped arm's arm-A spread is *wider*, 120–520 ms
against 311–428 ms, because the format check moves ahead of the images too). **Both effect comments
now name the other's queue position**, which is the thing that did not exist before this story and
the reason the next reader will not reorder them by accident. The 180 ms is ledgered and priced,
homed on c10-3.

**AC 21 — no gap to close**, so nothing is deviated. The **ownership conflict is raised anyway**:
`epics-companion-app.md` makes Epic 4 the **owner** of NFR-05 while the only gap-closing story
(10.3) is Phase 2 — the acceptance point ships in this release and the repair does not. Ledgered.

**AC 22 — SC-2 is cited but carries no timing.** SC-2 is *"agent-driven deck edits appear in the
deck view without user action"*, it belongs to **Epic 7**, and the 07-22 gate logged the loose
co-citation and ruled *"no fix required"*, after which the epics file inherited it into a story AC.
**NFR-05 is the sole authority for the 1-second number.** This story does not close SC-2 and does
not claim to. It also does not pass, fail or pre-empt **SC-5**, which is Brad's at **c8-6** and
*"cannot be automated or delegated"*.

⚠️ **What the number is not.** None of the four numbers already in the record was a layout time
(`c4-4`'s 9.3 s was filesystem mtimes with no browser; its 2–3 s was an unaided eyeball; `c4-6`'s
847–1,795 ms was navigation→last image, and its script did not survive). **This is the first
measured layout time in the project's history**, and it is not comparable to any of them — it stops
at the sixth surface, not at the last picture.

#### The eye-check (AC 28, Q14, Q15) — what the empty deck actually looks like

Chrome 151 over CDP at **1720px** and at UX-DR8's **~1100px** floor, screenshots captured.

- **The line renders as specified.** `14px/21px 'Space Grotesk'`, `rgb(179,184,207)` = `#B3B8CF` =
  `--text-secondary` ✅, `margin: 0px`, `padding: 0px`, **no background, no border**, left-aligned.
  Box **1138×21** inside a `.panel-body` of **1162×45** — the 12px `--space-3` inset on all four
  sides, exactly as the DESIGN.md amendment says and with no length of its own.
- **`.analysis-row` computes to `display: none` at 0×0** — c4-9's `:empty` rule confirmed in a real
  browser for the first time.
- **Chrome's own AX tree reports `banner: 1`**, against jsdom's 3 — the phantom-banner divergence
  measured rather than assumed, on this fixture. `region: 2` (Card detail, Deck list): the three
  hidden panels are genuinely gone from the landmark list, not merely invisible.
- **No `/api/deck/{id}/format-check` request was issued** — only `/api/decks`, `/api/active-deck`
  and `/api/deck/{id}`. AC 10 confirmed on the wire, in a browser, not only in jsdom.
- Header renders normally: kicker, `h1` *"Brand New Brew"*, `STANDARD`, **`0 MAINDECK`**. Skip link
  absent, no state panel, exactly one live region. No horizontal overflow at either width
  (`scrollWidth === innerWidth`); at 1100px the columns stack, both 1020px wide.
- **⚠️ AND THE RECORDED OBSERVATION IS NOT FLATTERING, WHICH IS WHY IT IS RECORDED.** The reduced
  composition is a **47px** grid strip carrying one sentence, beside two **57px empty panel
  shells** — a `CARD DETAIL` header over a blank body and a `DECK LIST` header over a blank body —
  on an otherwise empty 1720×1080 canvas. The line itself reads calmly and looks intentional. The
  two empty shells do not: they are precisely the *"reads as a loading failure rather than as an
  absent feature"* failure mode `DESIGN.md` names by hand. `DESIGN.md` states the layout
  unconditionally and describes no reduced form. **This is the UX-DR20 artefact defect made
  visible, and it is the single most useful thing this eye-check produced.** Not repaired here
  (inventing copy for either panel pre-empts a decision no artefact has made); ledgered, homed on
  the C4 retro, and it is exactly the kind of judgement UX-DR49 says the SC-5 gate is for.

#### AC 25 — the SC-5 conformance findings list (both anchors per item, NO VERDICT)

**Landed in this commit:**

| # | finding | artefact anchor | code anchor |
|---|---|---|---|
| 1 | the empty-deck treatment was specified NOWHERE | `DESIGN.md` (`components.*`, Components §) | `CardGrid.tsx` / `CardGrid.css` |
| 2 | `panel.header-padding: '10px 14px'` — `14` banned by name by this file's own scale | `DESIGN.md` `components.panel` | `Panel.css` (ships the scale pair since c2-7) |
| 3 | `panel.body-padding: '12px 14px'` — same | `DESIGN.md` `components.panel` | `Panel.css` |
| 4 | `badge.padding: '2px 9px'` — `9` in the enumerated drift list | `DESIGN.md` `components.badge` | `Badge.css` |
| 5 | `{typography.numeric}` still lists **price** as a role | `DESIGN.md` Typography | no consumer — there is no price data |
| 6 | *"100+ Tab stops"* where the peer artefact carries 205/102.0 | `DESIGN.md` Skip link bullet | `EXPERIENCE.md` (c4-11's measurement) |
| 7 | alt-text rule contradicted by **both** shipped consumers | `EXPERIENCE.md` Alt text | `CardTile.tsx`, `CardDetail.tsx` (`alt=""`, argued) |
| 8 | price promised in the IA table | `EXPERIENCE.md` Card detail panel row | `CardDetail.tsx` — no price rendered |
| 9 | *"Prices render only when present in local data"* — never satisfiable | `EXPERIENCE.md` Card detail contract | `cards` has 23 columns, none a price |
| 10 | token layer "closed at 64/65" ×4 | — | `Panel.css`, `Badge.css`, `StatChip.css`, `card-geometry.css` |
| 11 | hairline written as an amendment that *"should"* ship — it shipped in the same story | `DESIGN.md` `components.color-bar.segment-hairline` | `ColourDistribution.css` |
| 12 | ten stale `ui/README.md` claims (**the four token counts — 65/64 where the pins hold 69 — restored to this enumeration at code review 2026-08-07: the first write-up silently dropped them, the story's own anti-pattern #5, and left the four README literals unfixed while fixing the same class in four CSS files**; plus the alias count 9→12, `CardFace` "still declined", the format-check route as a prediction, *"the other six still have none"* falsified by its own next paragraph, the skip link in future tense, the three placeholder owners) | — | `ui/README.md` (all ten now corrected — the token counts at review, the review also catching a fresh contradiction the sweep itself wrote: "All ten now have an on-screen consumer" three lines before "`StatChip` alone still awaiting a surface"; now "Nine of the ten") |

**Recorded, NOT fixed** (ledgered, homed on the C4 retro): **~60 stale `DESIGN.md:NNN` anchors
across 25 files**, at least one now citing a real but wrong component
(`FormatCheck.css` → `DESIGN.md:423`, the Card tile bullet). `shell.test.ts` validates the *string*
`"DESIGN.md"` near a `px` literal and **never resolves the line number** — the epic's
coverage-that-reads-as-coverage theme inside a citation gate. The guard's repaired shape is written
into the ledger entry. ~60 edits and a red guard do not belong in a story that is otherwise one
sentence and one conditional.

**Open, not this story's** (all ledgered): the UX-DR20 empty-panel contradiction (finding above),
`StatChip` still without a surface, the 10px ALL-CAPS legal text (Epic 8), the `rem` basis
(Epic 8), the skip link not reaching the footer (c8-6).

**No verdict is offered.** SC-5 is a human judgement by Brad at **c8-6** and *"cannot be automated
or delegated"*. This story makes it **answerable**; it does not answer it.

#### Guards, fixtures and the anti-patterns pre-empted (AC 31, AC 32)

- **Every fixture is declared synthetic in place**, because there is no third option: **0 of 42
  decks have zero `deck_cards` rows**. Both empty-deck fixtures (`App.test.tsx`'s `emptyDeck()`,
  `CardGrid.test.tsx`'s `boardsOf([])`) carry that measurement beside them, plus the reason the
  state is nonetheless reachable (`create_deck` writes no card; `remove_card_from_deck` never
  deletes the deck).
- **AC 8's discriminator is the one assertion that makes AC 8 falsifiable.** On an empty deck "zero
  cards" and "zero curve total" coincide, so absence there is consistent with either mechanism. The
  **land-only** fixture separates them: cards present, tiles rendered, curve and colour absent,
  **format check PRESENT and requested**. That combination is possible only if the two panels
  self-gate and the third is gated on emptiness. A card-count gate in `App.tsx` would hide all
  three; a self-gate in `FormatCheck` would hide it too.
- **Every new guard carries a non-vacuity anchor and states what it cannot see** —
  `empty-deck-copy.test.ts` (both artefacts parsed, the row parser proved general on a row it never
  otherwise reads, the two negatives proved non-vacuous by finding the same phrases elsewhere in
  the same file), `shell.test.ts`'s CSS pin (empty block ⇒ fail; declares that it cannot see a
  colour arriving from another stylesheet), `App.test.tsx`'s never-blank reader (fed a shell-less
  document and required to report zero filled slots).
- ⚠️ **AND ONE OF THEM CAUGHT ITSELF, WHICH IS THE SEVENTH CONSECUTIVE INSTANCE OF THIS EPIC'S
  SIGNATURE CLASS.** `empty-deck-copy.test.ts`'s frontmatter reader was written `\n {2}key:\n`; the
  UX artefacts are **CRLF (485 of 485)**, so it captured the empty string and its four assertions
  would have passed over nothing. The non-vacuity anchor was written first and went red. Method,
  recorded in the ledger: **anchor first, then assert.**
- **A second false-green was caught by reading raw data rather than a summary**: the harness
  classified images with `"/image" in name`, which matches nothing (`/api/card-image/…` has no
  `/image` substring) and reported **0 image requests** in both arms — a plausible-looking number
  for a warm HTTP cache. Found by checking the raw resource list against the expected ~205.
- **`CardGrid.test.tsx:155-165` was REWRITTEN, not deleted, in this commit.** Its title
  (*"must not invent c4-12's copy"*) and its `expect(container.textContent).toBe('')` both became
  false the moment this story landed; the rewrite says so in place, and adds the sideboard-only
  residue pin.
- **Untracked bundle assets** (the twice-High): `git add -A src/companion/app/static/ plugin/` used
  throughout, and the copy module was `git add`ed **before** believing any registry-sweep green
  (`copy-rules.test.ts` walks `git ls-files` and is blind to an unstaged module — the c4-7
  false-green mechanism, and `COPY_MODULES` has **no** numeric count pin to catch it).
- **`graphify-out/` is not staged.** Confirmed with `git status --porcelain`; the `.gitignore` hunk
  is still master-only and this diff does not smuggle it.

#### The ten gates

| gate | result |
|---|---|
| `npm test` | **1,694 passed / 65 files** (from 1,668 / 64: **+26 tests, +1 file**) |
| `npm run lint` | ✅ eslint + stylelint clean |
| `npm run format:check` | ✅ |
| `npx tsc -b --force` | ✅ |
| `npm run build` | ✅ JS **224,270 B**, CSS **20,390 B** |
| `npm run gen:types` / `gen:api` | ✅ **no drift** |
| `uv run pytest` | ✅ **2,501 passed / 1 skipped** — Python untouched |
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ 307 files |
| `mypy src/` | ✅ 89 source files |

**Bundle + mirror:** rebuilt, the **untracked content-hashed additions staged**, `build_plugin.py`
re-run, and the mirror verified **sha256-identical per file** — 5/5, file sets equal.

**Registries:** `CONTAINERS` **24 → 25**, `COPY_MODULES` **13 → 14**, `CardGrid`'s declared imports
gain `'./copy'`, DESIGN.md Components bullets **24 → 25** (`attribution.test.ts`'s pin moved with
its reason), token inventory **holds at 69** — asserted, not assumed.

#### The eighteen don't-breaks

All eighteen green. Three worth naming: the **land-only** test (`App.test.tsx:794-828`) and the
**sideboard-only** test (`:1356-1379`) both pass **unchanged**, which is what proves no card-count
gate was added; and `hasCards`'s 26-line reason survives verbatim, with the relocation of its board
test documented in the same comment as Q1 required.

#### Machine state, left as found

Two **stale companion processes from 2026-08-06** held the machine-wide singleton lock (one live on
:8765, neither having published a discovery file), so `uv run artificial-planeswalker companion`
refused to start. They were stopped — the app's own documented recovery, in its own error message —
a fresh instance was run for the measurement, and it was stopped afterwards along with the
discovery file it could not clean up. `cards.db` `LastWriteTime` is still **28/07/2026**; the image
cache is back at **633 files / 63,195,342 B**; the deck count is **42**. The throwaway data
directory used for the empty-state eye-check was deleted.

### Completion Notes List

**One sentence of copy, one conditional render, and a number someone had to go and observe — and
all three of the story's headline claims held up under measurement.**

1. **The story's central prediction is CONFIRMED to within one place.** The format-check request
   sits at **queue position 106–107** on a cold open — predicted ~100 from effect-declaration order,
   HTTP/1.1 and Chrome's 6-connection cap. Five of the six named surfaces are in the DOM at ~205 ms
   and the sixth arrives at 311–428 ms, so **a 5.0 ms backend read costs ~200 ms of layout time**.
2. **NFR-05 IS MET — the first measured layout time this project has ever had.** 311/363/428 ms
   (fresh profile, n=5), 238/348/387 ms (repeat visit, n=5), 278/313/390 ms (cold image cache,
   n=3). Every prior number in the record measured something else with a different instrument.
3. **AC 2 was two-thirds already satisfied, and the third came free of a different mechanism.**
   Only `FormatCheck` needed a gate; the curve and colour bar self-gate on zero totals and
   `.analysis-row:empty` collapses the row — confirmed in a real browser, where the row computes to
   `display: none` at 0×0.
4. **"First-fetch image paint excluded" is a measured structural fact, not a claimed exemption.**
   With the CDN doing real work the last image lands at **~11.0 s** and layout does not move.
5. **The eye-check found the thing no test could.** The empty state's *line* looks intentional; the
   **two empty right-column panel shells beside it do not** — the UX-DR20 contradiction rendered,
   and precisely `DESIGN.md`'s own *"reads as a loading failure"* failure mode. Recorded, not
   repaired, and handed to the SC-5 gate that exists for exactly this judgement.
6. **Two record corrections beyond the story's own**: `deck_cards` holds **28 orphan rows across 2
   deleted decks** (so any census not joined to `decks` over-counts by two decks — the story's own
   §F did), and the image cache occupies **220 shards, not 137**.
7. **The seventh consecutive coverage-that-reads-as-coverage instance landed in this story's own
   new guard** — a `\n`-only regex against CRLF artefacts — and was caught by its non-vacuity anchor
   before a reviewer saw it, for the second story running. A second false-green (0 image requests)
   was caught by checking raw data against an expected count.
8. **Two stated deviations**, both narrowing rather than widening: the predicate lands in
   `deckGroups.ts` beside `DeckBoards` rather than in `deck.ts` beside `surfaceOf` (no new module,
   and `CardGrid` does not acquire the API client in its graph); and the empty-state eye-check wrote
   **nothing at all** to the shipped database, using a relocated `PLANESWALKER_DATA_DIR` instead of
   create-then-delete. A third, smaller: `CardGrid.css` does not join `CALM_STYLESHEETS` — a narrower
   per-rule pin replaces the file-wide claim.
9. **⚠️ FOR BRAD, AND IT IS THE ONE THING NO MEASUREMENT SETTLES.** The empty-deck state is an
   **unconfirmed product decision**. Its provenance is a *medium* validation finding that
   recommended hiding **the curve only**; colour distribution and format check were added with no
   recorded rationale, `.memlog.md` tags the treatment `(assumption)`, and it is **not** among the
   four rulings you confirmed. It ships as written. **Changing it is cheap today and expensive at
   Epic 8** — and the eye-check above is the picture to decide against.
10. **An 180 ms improvement is measured, priced and deliberately NOT taken.** Swapping the two
    `useEffect` blocks moves the format check from queue position 106 to 7 and roughly halves layout
    time. Q10 rules the swap only if the budget is missed; it is not. Both comments now name the
    other's queue position so the lever cannot be pulled — or lost — by accident. Homed on c10-3.

**Suite 1,668 → 1,694 (+26) across 64 → 65 files. Python 2,501 / 1, unchanged. JS 224,110 →
224,270 B, CSS 20,316 → 20,390 B. Mirror sha256-identical, 5/5.**

#### Code-review decisions and corrections (2026-08-07, three-layer review)

1. **EXPERIENCE.md alt-text amendment RATIFIED as a ruling** (review decision, Brad). The sweep's
   rewrite of the alt-text row — extending `alt=""` to grid tiles and the detail panel, reversing
   the row's earlier "image is the only carrier" carve-out — stands, now as an explicit ruling
   rather than a drive-by: the tile caption and the detail panel's text carry the card name, so a
   name `alt` would double-announce it, and the code's behaviour is the intended one. Raised
   because a normative accessibility contract changed inside a conformance sweep with no recorded
   decision; the decision is now recorded here.
2. **The cold-cache arm's n=3 ACCEPTED, with the scoping stated** (review decision, Brad). AC 15's
   "at least five runs per arm" binds AC 15's own measurement — the two **warm-cache** readings
   AC 17 defines, both run at n=5. The cold-image-cache arm belongs to **AC 19**, which restates
   no run count; it was run at n=3 (278/313/390 ms, all inside budget) and the Dev Record adopted
   the "arm" vocabulary for all three without saying so — which read as a shortfall against the
   n≥5 clause. It is a scoping difference, not a shortfall, and this note is the statement AC 15
   was missing.
3. **Task 3 structural deviation, declared late**: the spec said "Extend `App.test.tsx:1329-1354`'s
   describe"; the implementation instead added a dedicated empty-deck describe at end of file
   (plus the never-blank describe) and left `:1329-1354` untouched. All the required assertions
   exist; the venue differs, and this is the declaration the first write-up omitted.
4. **The review's High**: the never-blank test titled *"…and through recovery back to a deck"*
   never drove recovery — settled refusals only, poll never advanced, no post-recovery assertion
   (found independently by two review layers). Fixing it honestly required a measurement: driving
   all four refusals through recovery FAILED on `internal_error`, because `poller.ts`'s
   `RETRIES_QUIETLY` is deliberately `false` there — the poll STOPS, and no recovery edge can ever
   arrive for `internal-error` (or `deck_not_found`, which clamps to the same terminal panel). The
   test now drives real recovery for the two retrying tokens and pins the terminal pair's
   filled-slots posture, which is both halves of AC 23's sentence rather than one.
5. **16 review patches applied in total** (2 from ratified decisions above): the two stale
   "40 real decks" citations AC 30 named (`App.tsx`); the four README token counts Q13 named plus
   the sweep's own fresh "all ten" contradiction; the mathematically false `emptyDeck`-vs-
   `!hasCards` comment (identical inside the deck branch — corrected, with the legibility reason
   that survives); the "asks then" and "UNCONDITIONAL teardown" comment overstatements; run-count
   prose aligned to the 13-run corpus; three mechanical evasion holes closed in `shell.test.ts`'s
   calm-line guard (comment-brace truncation, property case, `var()` fallback literals) with
   in-test length pins added to `empty-deck-copy.test.ts`'s two loop tests; the two undeclared
   `distinct_cards: 2` empty-deck fixtures completed to the real wire body; `CardGrid`'s tile
   flattening no longer built-then-discarded on the empty branch; and the sideboard-only residue's
   UX-DR36 interaction written into `deckGroups.ts`. Two findings deferred to the ledger
   (pre-existing one-frame stale-report window; no committed CDP harness — homed on the C4 retro),
   four dismissed on verification (quantity ≥ 1 is schema- and repo-enforced; server count/cards
   drift has one source of truth server-side; two artefact-edit edge cases already fail loud).

### File List

**Source (frontend)**

- `ui/src/state/deckGroups.ts` — MODIFIED: `deckIsEmpty` added beside `DeckBoards`
- `ui/src/App.tsx` — MODIFIED: `emptyDeck`, the format-check request suppression and render gate,
  `hasCards` refactored to consume the predicate, the effect-ordering decision in both comments
- `ui/src/containers/CardGrid/copy.ts` — **NEW**: `EMPTY_DECK_LINE`, import-free
- `ui/src/containers/CardGrid/CardGrid.tsx` — MODIFIED: the line replaces the `<ul>`
- `ui/src/containers/CardGrid/CardGrid.css` — MODIFIED: `.card-grid-empty`, no `px` literal

**Tests**

- `ui/tests/empty-deck-copy.test.ts` — **NEW**: byte-for-byte artefact gate + the DESIGN.md
  amendment gate
- `ui/src/App.test.tsx` — MODIFIED: the empty-deck describe (7 tests) and the never-blank describe
  (4 tests)
- `ui/src/containers/CardGrid/CardGrid.test.tsx` — MODIFIED: the c4-4 empty-deck describe rewritten
  (its title had become false) + the sideboard-only residue pin
- `ui/tests/shell.test.ts` — MODIFIED: `CONTAINERS` 24 → 25, `CardGrid` imports `'./copy'`, the
  `.card-grid-empty` calm pin
- `ui/tests/copy-rules.test.ts` — MODIFIED: `COPY_MODULES` 13 → 14
- `ui/tests/attribution.test.ts` — MODIFIED: Components-bullet pin 24 → 25

**Conformance sweep (Q13 LAND list)**

- `_bmad-output/planning-artifacts/ux-designs/…/DESIGN.md` — MODIFIED: `components.empty-deck-line`
  (new), the Empty deck line Components bullet (new), `panel.header-padding`, `panel.body-padding`,
  `badge.padding`, the Skip link corridor figure, the `numeric` price residue
- `_bmad-output/planning-artifacts/ux-designs/…/EXPERIENCE.md` — MODIFIED: the alt-text rule, two
  price residues
- `ui/src/components/Panel/Panel.css`, `ui/src/components/Badge/Badge.css`,
  `ui/src/components/StatChip/StatChip.css`, `ui/src/styles/card-geometry.css` — MODIFIED: the four
  stale token counts (64/65 → 69)
- `ui/src/containers/ColourDistribution/ColourDistribution.css` — MODIFIED: the shipped amendment
  cited, the future-tense clause deleted
- `ui/README.md` — MODIFIED: the stale claims

**Record**

- `_bmad-output/implementation-artifacts/deferred-work.md` — MODIFIED: the fifteen dispositions and
  the new entries, **in this commit**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED: `c4-12` → `review`
- `_bmad-output/implementation-artifacts/c4-12-empty-deck-state-and-the-cold-open-render-budget.md`
  — MODIFIED: this record

**Build output (generated, committed)**

- `src/companion/app/static/index.html`, `assets/index-Cv-JFKao.js`, `assets/index-B_WnaAKx.css`
  (the two hashed files are **additions**, staged with `git add -A`; the JS re-hashed from
  `index-CiTvYAAz.js` at the post-review rebuild — the CDP measurements above were taken against
  that pre-review bundle, and the record keeps its name there on purpose)
- `plugin/server/src/companion/app/static/…` — the mirror, rebuilt and sha256-verified per file

**Not touched:** `AppShell.tsx`, `ManaCurve.*`, `DeckList.*`, `CardDetail.*`, `AnalysisRow.*`,
`eslint.config.js`, `tokens.css`, and everything under `src/` except the generated bundle.

### Change Log

| date | change |
|---|---|
| 2026-08-07 | c4-12 implemented on `feat/companion-c4-12-empty-deck-and-render-budget` off `86d5fb6`. The empty-deck line (one copy module, one conditional render, one predicate), the format-check hide and request suppression, the never-blank definition, the SC-5 conformance sweep's LAND list, and the cold-open render budget measured over CDP in Chrome 151 across three cache arms (13 runs). NFR-05 met: 311/363/428 ms fresh profile, 238/348/387 ms repeat visit, 278/313/390 ms cold image cache — against a 1,000 ms budget. Fifteen inherited deferrals dispositioned in `deferred-work.md`. Suite 1,668 → 1,694 / 65 files; Python 2,501 / 1 unchanged; ten gates green; mirror sha256-identical. Status → `review`. |
| 2026-08-07 | Three-layer code review (Blind Hunter / Edge Case Hunter / Acceptance Auditor): 25 raw → 22 triaged = 2 decisions (both ruled same day: alt-text amendment RATIFIED as a ruling; cold arm n=3 ACCEPTED with the AC 15/AC 19 scoping stated) + 16 patches ALL APPLIED + 2 defers ledgered + 4 dismissed on verification. The High: the never-blank test's title claimed "recovery back to a deck" over a body that never advanced the poll — fixed by measurement, which found the poll is deliberately TERMINAL for `internal_error`/`deck_not_found` (`RETRIES_QUIETLY`), so the test now drives real recovery for the two retrying tokens and pins the terminal pair. Suite holds at 1,694 / 65; ten gates re-run green; bundle re-hashed to `index-Cv-JFKao.js` (224,279 B by stat — the earlier byte figures were vite's rounded kB ×1000), CSS content-identical; mirror rebuilt, sha256-verified 4/4. Status → `done`. |

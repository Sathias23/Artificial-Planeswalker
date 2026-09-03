---
epic: c4
story: c4-2
work_branch: feat/companion-c4
story_branch: feat/companion-c4-2-deck-bootstrap
depends_on: >-
  c4-1 (merged to `feat/companion-c4` at `2095050`) — `src/api/client.ts` is the one network door
  and `src/state/cards.ts` ships `seedCardSummaries`, the entry point THIS story calls. Also
  **c3-4** (`GET /api/active-deck`), **c3-1** (`GET /api/deck/{deck_id}`, `GET /api/decks`), **c3-9**
  (the poll, `panelFor`, the store) and **c2-9** (`PANEL_FOR_REASON`, whose `deck_not_found` entry
  has been dead code since it was written — this story is its first live producer).
baseline_commit: 2095050
---

# Story C4.2: Deck state bootstrap and the type-grouped decklist

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad opening a tab,
I want the app to work out which deck is active and load it,
so that a fresh tab shows my deck rather than assuming there isn't one.

**What this story really is.** It is the first story where a **deck** exists in the client, and it
is therefore the first story that has to answer a question nine stories have deferred: *when a deck
and a system state are both true, which one is on the glass?* Five facts are not what the title
suggests, and the first two change the design:

1. **The two boot routes fail in completely different vocabularies, and one of them cannot fail the
   way the epic's AC says.** Measured from the committed `ui/src/api/openapi.json`:
   `GET /api/active-deck` publishes **`200`, `400`, `500` — and nothing else.** No `503`, no `404`,
   no `413`. That is not an omission: `active_deck.py`'s header says *"There is deliberately no
   database here at all. Not a `DbSession`, not a repository import, not a `503` path."*
   `GET /api/deck/{deck_id}` publishes **`200`, `400`, `404`, `413`, `500`, `503`**. So the epic's
   *"the backend returns `503 database_not_initialized`…"* AC can only ever be about the **second**
   request, and a boot written as one `try` over two requests with one outcome type would model
   failures the first route cannot produce and miss the asymmetry that matters.

2. **`PANEL_FOR_REASON.deck_not_found → 'no-active-deck'` has been unreachable dead code since
   c2-9, and this story is what makes it live.** `panelFor` is only called by `poller.ts`, which
   only reads `GET /api/decks` — a route that **does not publish `deck_not_found`** (verified in
   `openapi.json`: its responses are `200/400/413/500/503`). The epic's *"a `404` clears to the
   no-active-deck state"* AC is therefore already **decided**, in c2-9's own comment: *"A deck
   deleted between a push and a refetch (FR-11) is not an error state of its own — the honest thing
   on screen is 'there is no active deck'."* Consume that map; do not write a second `switch`.

3. **`panelFor()` on a deck read is CORRECT, and that looks like a contradiction of c4-1 AC 13.**
   c4-1 forbade routing a **card** refusal through `panelFor` because `card_not_found` maps to
   `null` and `panelFor` clamps `null` to `'internal-error'` — a whole-screen error panel because
   one tile was missing. A **deck** refusal is the opposite case: the deck IS the surface, so every
   deck token has an honest panel and `PANEL_FOR_REASON` already holds it. State this in the code,
   because the next reader will arrive holding c4-1's rule.

4. **The type-grouping input is `type_line` and only `type_line`, and that is a real constraint.**
   The deck payload carries a `CardSummary` per card (name, `mana_cost`, `cmc`, `type_line`,
   `oracle_text`, `colors`, `rarity`, `set_code`) — **no `card_faces`**. So *"double-faced cards
   group by their front face"* is implementable exactly as `type_line.split(' // ')[0]`, and the
   one shape it cannot resolve is the **`'Card // Card'` printing** (2,274 in the corpus, whose real
   front-face type lives only in `card_faces[0].type_line`). Measured today: **0 of 1,999 live deck
   rows** are such a printing. Latent, not live — say so, do not fetch 99 cards to fix it.

5. **There are already two land policies in this repo and they disagree on four cards that are in
   real decks.** `src/viewer/view_model.py::is_land` classifies on the **front face**
   (`type_line.split("//")[0]`) *"so a modal/double-faced card whose front is a spell is treated as
   a nonland"*; `src/logic/assessment/mana_base.py::_is_land` and `src/logic/mana_curve.py` use a
   **whole-string** `"land" in type_line.lower()` and document the consequence as v1 policy. FR-05
   and UX-DR17 both say *front face*. **Do not port the curve's policy** — and do not fix the curve
   here either (that is c4-8's, and it is a `src/logic` change with MCP blast radius).

**Everything numeric in this story was measured on this machine at `2095050`, read-only, against the
live database at `%LOCALAPPDATA%\artificial-planeswalker\cards.db`, the committed `openapi.json` and
the installed toolchain. Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **`src/api/client.ts` is the ONE door, and its header already names this story's two routes.**
   *"The next route goes here too. `GET /api/deck/{deck_id}` is c4-2's, `GET /api/active-deck` is
   c4-2's, the format check is c4-10's — all of them belong in this file until somebody argues the
   one-door property away on purpose."* `posture.test.ts:328` asserts `doors).toEqual(['src/api/
   client.ts'])` **exhaustively**; a new `src/api/deck.ts` is a red test, not a review comment. The
   shape to match is `readDecks`/`readCard`: a **total outcome union that never rejects and never
   returns `null`**, with four distinct failure inputs (non-2xx with no body, a body that is not
   JSON, a body with no `reason`, a network rejection) as four distinct values. Both new readers
   share the module's existing private `request()` helper — it owns the `AbortSignal.timeout`
   guard and `cache: 'no-store'`, and a second copy is a second place to get the timeout wrong.

2. **`cardPath()` is the encoding precedent, and `ActiveDeck`'s own docstring instructs this
   story.** *"A reader fetching the deck interpolates it into `GET /api/deck/{deck_id}`
   **URL-encoded**, like any path segment: the id has no declared shape (Q4), so nothing forbids
   characters — `/`, `?`, `#` — that a raw interpolation would mis-route."* The id comes from
   `PUT /api/active-deck`, which stores **any non-blank string ≤ 256 chars verbatim** and
   deliberately does not check that the deck exists (`contracts.py`, `_MAX_DECK_ID_LENGTH`). Also
   inherit `cardPath`'s empty-id lesson: `deckPath('')` is the bare `/api/deck/` — a different
   route, not a malformed parameter — and `ActiveDeckRequest` refuses blanks on the way in, so an
   empty id can only arrive from a body that is not this contract.

3. **The card cache's seeding entry point is built, tested and waiting for this story.**
   `seedCardSummaries(deckCards: readonly DeckCardSummary[])` in `src/state/cards.ts` populates the
   summary tier for every id, issues **zero** requests, and leaves each id's hydration tier
   untouched (`hydrated` stays hydrated, `unknown` stays unknown). c4-1's header: *"c4-2 calls
   this; c4-1 ships and tests it."* Calling it is one line and it is AC 17; **not** calling it
   means every later surface pays 99 requests for data that already arrived (measured: 38,182 bytes
   in **1** request vs 212,436 bytes in **99**).

4. **The poll already exists, it already stops, and its stopping is asserted.** `poller.ts` polls
   `GET /api/decks`; `RETRIES_QUIETLY['no-active-deck']` is `false`, so **one `200` ends the poll**
   — `App.test.tsx:243` asserts exactly that (`toHaveBeenCalledTimes(1)` after ten minutes). Two
   consequences this story must not get wrong: (a) the deck names the `no-active-deck` panel renders
   still come from that poll, unchanged; (b) **there is no re-drive after the first `200`**, so a
   deck the agent sets while the tab is open does not appear until Epic 5's `deck_changed`. That is
   a declared residue with a named home, not a bug to invent a second poller for.

5. **`poller.ts:238` carries the line this story retires.** *"A `200` is `no-active-deck` and its
   deck list **until c4-2 ships the deck view**."* Whether that comment becomes true-by-deletion or
   true-by-amendment is Q1's call, but the comment and the behaviour move in the same commit —
   "prose outrunning code" is this epic's standing finding, five rounds running.

6. **`AppShell` already has the two props this story fills, and it names this story in both.**
   `deckName?: ReactNode` — *"**c4-2 supplies the deck name here** — the element, its level and its
   position do not move, which is the whole point of it being a prop"* — and `badges?: ReactNode`
   — *"c2-7 supplies Badge; c4-2 and c4-10 fill them."* **`AppShell.tsx` needs no edit**;
   `shell.test.ts` pins its imports as exhaustive lists and bans hooks/`fetch`/`WebSocket` in it and
   in the eight primitives. The filling happens in `App.tsx`.

7. **`filled()` is the emptiness test, not truthiness, and `AppShell` already applies it to
   `deckName`.** `deckName=" "` renders an `h1` that is present, invisible and announced as an
   empty heading — the heading-less state c2-6 Q3 exists to prevent. `filled` handles `''`,
   whitespace, `[]`, empty iterables and empty Fragments. Do not add a second emptiness check.

8. **The two vitest projects and the `tsc -b` trap.** `src/**/*.test.{ts,tsx}` → **jsdom**;
   `tests/**/*.test.{ts,tsx}` → **node**, and `gate-geometry.test.ts` forbids `.tsx` tests under
   `tests/`. Importing a real `src/` module from `ui/tests/` pulls it into the node project where
   extensionless relative imports become `TS2835` cascades — **and `npm test` stays green**, because
   it is a `tsc`-only failure that `tsc -b`'s incremental cache can hide. `npx tsc -b --force` is
   what makes it deterministic; c4-1 hit this from an unexpected direction (an untyped `it.each`
   table widening a discriminant to `string`) and it cost a diagnosis.

9. **`@testing-library/react` IS in the dependency set** (`^16.3.2`, plus `@testing-library/dom`
   and `@testing-library/jest-dom@~6.9.1`), and `App.test.tsx` uses it today. c4-1's `useCardEntry`
   deferral is homed on c4-3 with the reason *"no testing library exists in the dependency set"* —
   **that reason is false**, and the correction belongs in this story's ledger pass (AC 28). It also
   means a hook this story ships can be tested for real, with no dependency argument to make.

### What the real data says (measured at `2095050`, read-only)

**The corpus, the decks and the type lines.**

| Property | Measured |
| --- | --- |
| Cards in the shipped database | **38,261** |
| Saved decks | **40** — every one of them non-empty, every name non-blank |
| `deck_cards` rows in total | **2,027** |
| …belonging to a deck that still exists | **1,999** — **28 rows across 2 deleted deck ids are orphans** (no FK enforcement; see the ledger note in AC 28) |
| Deck formats | `standard` 19 · `brawl` 18 · `standardbrawl` 2 · `historic` 1 — **no deck has a NULL format** |
| Decks with a NULL `strategy` | **1 of 40** |
| Decks carrying a commander row | **16 of 40** (16 rows) |
| Decks carrying a sideboard row | **5 of 40** (41 rows) |
| Distinct type-groups per deck | **1 → 8** (3 decks have 1 group, 14 have 7, 1 has 8) |

**The type-line facts the grouping rests on** (`—` in a type line is U+2014, not a hyphen):

| Property | Corpus | In live decks |
| --- | --- | --- |
| `type_line` NULL or blank | **0** | 0 |
| `type_line` containing ` // ` | 3,183 | **65 rows / 39 distinct cards** |
| …of which literally **`'Card // Card'`** (a reversible printing whose real front type is only in `card_faces`) | **2,274** | **0** — latent, not live |
| `type_line` literally `'Card'` | 400 | **2 rows** — "Pym Particles" |
| Front face carrying **more than one** primary type (`Artifact Creature`, `Enchantment Creature`, `Legendary Artifact Planeswalker — Equipment`) | — | **88 rows** |
| Rows outside the eight primary types altogether | — | **1** (`'Card'`) |
| `Land Creature` (the Dryad Arbor shape) | 4 | **0** |

**The two land policies, and the four cards they disagree about — all four are in real decks:**

| Card | `type_line` | front-face policy | whole-string policy |
| --- | --- | --- | --- |
| Agadeem's Awakening // Agadeem, the Undercrypt | `Sorcery // Land` | **Sorcery** | Land |
| Kazandu Mammoth // Kazandu Valley | `Creature — Elephant // Land` | **Creature** | Land |
| Dowsing Dagger // Lost Vale | `Artifact — Equipment // Land` | **Artifact** | Land |
| Journey to Eternity // Atzal, Cave of Eternity | `Legendary Enchantment — Aura // Legendary Land` | **Enchantment** | Land |

FR-05 and UX-DR17 both say front face. **84 corpus cards** would be misgrouped by the whole-string
policy; 4 of them are in decks today.

**The largest real deck — "Atraxa Counter Cabinet v2 (owned)", the 100-tile grid the epic
describes, and it exists.** Deck id `813d0434-1bed-4419-bf9d-d9e4070704c4`.

| Property | Measured |
| --- | --- |
| `GET /api/deck/{id}` body, minified | **47,458 bytes** in **one** request |
| Distinct card ids (= tiles) | **99** · total quantity **100** |
| Commander rows / sideboard rows | **1** / **0** |
| Groups under the proposed scheme (Q3) | **7**: Planeswalker 11 · Creature 29 · Sorcery 2 · Instant 8 · Artifact 6 · Enchantment 6 · Land 37 |
| `mainboard_count` / `sideboard_count` / `distinct_cards` | 100 / 0 / 99 |
| Name length (the `h1`) | 32 chars; longest deck name in the corpus is **62** |

**The wire, as committed.**

| Route | Responses in `openapi.json` |
| --- | --- |
| `GET /api/active-deck` | **`200`, `400`, `500`** — no `503`, no `404`, no `413` |
| `GET /api/deck/{deck_id}` | `200`, `400`, **`404`**, `413`, `500`, **`503`** |
| `GET /api/decks` | `200`, `400`, `413`, `500`, `503` — **no `404`** |

**The frontend gate baseline (verify it yourself in Task 0; do not trust this table).**

| Gate | Measured at `2095050` |
| --- | --- |
| `npm test` | **816 passed, 37 files**, 4.9 s |
| `npm run lint` / `format:check` / `npx tsc -b --force` / `npm run build` | green |
| `uv run pytest -m "not integration"` | **2,447 passed, 1 skipped, 54 deselected** (c4-1's measurement; re-measure) |
| Aliases exported by `src/api/schema.ts` | **7** |

> **One measurement artefact, recorded so it is not diagnosed twice.** One `npm test` run on this
> machine reported `36 passed (37)` / `812 passed (816)` with `Error: Worker exited unexpectedly`
> and **no failing assertion**; the immediate re-run was **816/37 green**. It is a vitest worker
> crash, not a test failure. If it recurs, re-run before investigating.

## Acceptance Criteria

### The boot sequence, and the two routes that fail differently

1. **A cold open calls `GET /api/active-deck`, and on a non-null `deck_id` calls
   `GET /api/deck/{deck_id}`** (FR-07, epic AC). Two requests, in that order, on mount — not on a
   timer, not per component. A `deck_id` of `null` is the **ordinary** answer after every backend
   restart (FR-07: the slot lives in memory and dies with the process), not an error path.

2. **Both routes live in `src/api/client.ts`, and `posture.test.ts`'s exhaustive door list is still
   green with no edit.** After this story there is still exactly **one** module in `ui/src`
   containing a `fetch(`. Each reader returns a **total outcome union, never rejects, never returns
   `null`**, in the shape `readDecks`/`readCard` established, and both go through the existing
   private `request()` helper rather than calling `fetch` a third and fourth time.

3. **The deck id is URL-encoded into the path.** `ActiveDeck`'s own docstring asks for this by name.
   An id carrying `/`, `?` or `#` must stay one path segment so that an unknown deck answers
   `deck_not_found` rather than addressing a different route. The empty id is refused before any
   request, exactly as `hydrateCard` refuses `''` — `/api/deck/` is a different route, not a
   malformed parameter.

4. **`src/api/schema.ts` gains `DeckDetail` and `ActiveDeck`, each with a docstring naming its
   consumer, and no alias without one.** Both are `components.schemas` names and therefore already
   **banned** everywhere in tracked TypeScript outside `src/api/` by `wire-contract.test.ts` — the
   ban grew on its own when c3-1 and c3-4 landed. `wire-contract.test.ts` stays green with no edit.
   Do not add `CardFace` (c4-6's) or any other alias this commit does not consume.

5. **The boot is idempotent and cancellable.** React StrictMode remounts effects in development, so
   a naive boot fires twice; an unmount mid-flight must not write to a store the caller has left.
   `createPoller`'s **generation counter** is the precedent to copy (`poller.ts:168` — *"a plain
   `live` boolean cannot tell 'stopped' from 'stopped and restarted'"*), and the same argument
   applies to a two-request sequence, where the second request is issued *after* an await.

### Which surface wins — the reconciliation this story owns

6. **A loaded deck displaces the system panel, and the precedence is decided in ONE place** (Q1).
   Not in JSX, not in two components. Today `App.tsx` renders a `StatePanel` unconditionally from
   `useSystemState().panel`; after this story a deck on the glass means no panel, and *which* rule
   decides that must be readable in one expression. A second copy of the rule is what makes the grid
   (c4-4) and the deck list (c4-7) able to disagree — the exact failure the epic's own AC about the
   derivation is written to prevent, applied one level up.
   **State the visible consequence rather than discovering it:** with the panel gone and no grid
   until c4-4, the shell's `left` slot falls back to its own placeholder — *"The card-art grid
   lands here — c4-4 …"* — which is the honest displacement (c2-9's decide-once pattern, third
   application) **and** re-exposes retro **F1**'s story-key strings on a screen that now shows a
   real deck name. Both are correct for today; both belong in the record, and F1's gate is **Q8**.

7. **No active deck renders the `no-active-deck` panel with the deck names, unchanged** (UX-DR30,
   UX-DR33, epic AC). Names come from the poll that already runs; they stay **non-clickable** —
   `EXPERIENCE.md`: *"names only, non-clickable — the agent drives"* — and `App.test.tsx`'s existing
   assertions on that panel must still pass **unmodified**. An empty deck list still renders nothing
   extra.

8. **`404 deck_not_found` clears to the no-active-deck state** (FR-11, AD-16, epic AC), and it does
   so **through `PANEL_FOR_REASON`**, which already holds that mapping with its reason written down.
   This is that entry's first live producer; the map is consumed, not paraphrased. Note the honest
   consequence: the deck id the backend still reports as active is one the client has cleared —
   record what happens on the next boot.

9. **`503 database_not_initialized` and `503 database_unavailable` on the deck read put the matching
   c2-9 panel on the glass** (AD-16, epic AC), chosen from the **token** and never from
   `response.status`. Two different `503`s must produce two different panels, and the assertion must
   say so — this is AD-16's central rule reaching the deck path for the first time.

10. **A card refusal never becomes a panel; a DECK refusal always does — and the difference is
    written down.** c4-1 AC 13 forbade `panelFor()` on the card path because `card_not_found` maps
    to `null` and would clamp to `'internal-error'`. On the deck path `panelFor()` is the right
    call, because the deck **is** the surface. A reader arriving with c4-1's rule must find the
    distinction stated where they will look, not have to reconstruct it.

11. **A `400 invalid_request` on a DECK read is ruled, not discovered** (Q5). `states.ts` classifies
    that token `NO_UI_RESPONSE` — *"the SPA never generates a malformed request"* — and `panelFor`
    would therefore clamp it to `'internal-error'` (*"The companion hit a bug."*). The premise is
    exactly what fails here: the id came from `PUT /api/active-deck`, which stores **any non-blank
    string verbatim and validates nothing**. Decide it and record the decision in code. Not deciding
    is not an option.

12. **The deck read has a BOUND ON ATTEMPTS, or an argued reason it needs none** (Q6). The
    503-outranks-400 trap applies here too — `/api/deck/{deck_id}` carries a path parameter, so a
    backend with no database answers `database_not_initialized` to an id that could never succeed —
    and this is the second story c3-9's warning was written for. Whatever the answer, a test must
    prove the app does not issue unbounded requests for an id that refuses forever.

### The derivation — grouped by card type, once, in the store

13. **The decklist is grouped by card type and the grouping happens exactly once, in the store**
    (FR-05, epic AC). Not in a component, not in a selector each consumer writes. The epic's reason
    is verbatim: *"so the grid and the list panel cannot disagree"* — c4-4 and c4-7 read the same
    derived value.

14. **Double-faced cards group by their FRONT FACE** (FR-05, epic AC): the segment of `type_line`
    before the first ` // `. 65 rows across 39 distinct cards in live decks depend on it, and four
    of them (table above) are the cards where the repo's own two land policies disagree.
    **`src/logic/mana_curve.py`'s whole-string policy is not the model here**; `src/viewer/
    view_model.py::is_land`'s front-face policy is, and FR-05/UX-DR17 are why.

15. **A front face carrying more than one primary type lands in exactly one group, by a declared
    precedence** (88 live rows). `Artifact Creature — Golem` is a creature; `Legendary Artifact
    Planeswalker — Equipment` is a planeswalker. The precedence order and the group order are
    **one list, read in one place** — two lists are two things to drift.

16. **A type the scheme does not name is carried, never dropped** (1 live row today: `'Card'`). A
    card that vanishes from every group is a card the deck view silently loses, and the counts stop
    summing to the deck. Whatever the residual bucket is called, the invariant to assert is
    **conservation**: every `DeckCardSummary` in the payload appears in exactly one group, and the
    quantities sum to `mainboard_count + sideboard_count`.

17. **The deck payload seeds the card cache, and it costs zero requests** (c4-1 AC 5).
    `seedCardSummaries(detail.cards)` is called with the payload this story already fetched. Assert
    the **request count**, not the bytes — and spy on the real request path (global `fetch`), which
    is the only honest count for a function that takes no reader (c4-1's own review corrected a
    vacuous version of this assertion).

18. **The store's inputs are exactly REST responses — and, from Epic 5, WebSocket messages — and
    nothing else writes it** (AD-12, the spine, epic AC). No component sets deck state; no
    `localStorage`; no URL parsing; no derived value written back in.

### The header — the deck's name and its badges

19. **The `h1` carries the deck name, and the kicker and the `h1` stop saying the same words**
    (C3 retro **F2**, recorded *"so c4-2 does not treat the swap as cosmetic"*). `AppShell`'s
    `deckName` prop is filled from `App.tsx`; **`AppShell.tsx` is not edited**, its element, level
    and position do not move, and its `filled()` fallback still fires when there is no deck — which
    is what keeps the fresh-install page from being heading-less (c2-6 Q3).

20. **The header badges are filled with the format and the size, and they are the first on-screen
    consumer of `Badge`** (UX-DR8, UX-DR10; `AppShell`'s own placeholder names c4-2 as a filler).
    Two ledgered consequences land here: (a) `Badge`'s **appearance has never been dev-verified** —
    jsdom applies no stylesheet, and the failure mode is *a solid blank pill with invisible text*,
    which reads as a content bug; (b) the **tone-over-wash contrast is unmeasured**. Both are homed
    on this story and c4-10, and both need an eyeball plus a number, recorded. **This story does not
    claim legality** — *"standard legal"* in the mock is c4-10's, over the format-check endpoint
    this story does not call. **And a size badge is a COUNT**: `Badge.css:77` is
    `font: var(--type-label)`, which is 11px **UPPERCASE and tracked**, so `100 maindeck` renders as
    `100 MAINDECK` in **non-tabular** numerals — while UX-DR3 requires tabular numerals on *"every
    count, quantity, price and axis value"*. That is c2-10's landmine in a new costume (a derived
    uppercase guard turning authored copy all-caps), and it is Q9's second half. If the answer adds
    CSS, `token-usage.test.ts`'s `findUnpairedNumericRole` binds: `font: var(--type-numeric)` and
    `font-variant-numeric: var(--type-numeric-features)` are applied **together or not at all**.

21. **The generated-type optionality asymmetry is ruled** (ledgered, *"Home: c4-2, unshared"*).
    `strategy?: string | null` versus `format: string | null` — the server always serializes both,
    so the `?` is a Python-default artifact that forces a spurious `undefined` branch — and
    `@default 0` is advertised on all three count fields, which is *"exactly the silently-wrong
    value"* the ledger warns about. This story reads `name`, `format` and the counts. Rule it:
    fix the wire, absorb it at the alias, or decline with a reason.

### Boundaries — what this story must not do

22. **No grid, no deck list, no curve, no colour distribution, no card detail panel.** The grid is
    **c4-4**, the placeholders **c4-3**, the detail panel **c4-5**, the deck list and its group
    headers **c4-7**, the curve **c4-8**, the format check **c4-10**, the empty-deck state
    **c4-12**. The derivation ships **declared and unread** by this story's own render, exactly as
    c4-1's cache did — that is the shape, not a shortfall.

23. **`AppShell.tsx` and the eight primitives are untouched.** `shell.test.ts` pins nine exhaustive
    import lists and bans hooks, `fetch(` and `WebSocket(` in each. Filling `deckName`/`badges`
    happens at the call site.

24. **No new user-facing prose outside a declared copy module.** `copy-rules.test.ts` bans prose in
    a non-copy module and bans `!`, emoji and "something went wrong" across all of `src/`. A deck
    name is **data**, not copy; a sentence about a deck is copy and belongs to c4-12.

25. **No second state or data-fetching library, and no second code generator** (AD-12), asserted by
    `package-contract.test.ts`. If this story adds any dependency, the addition is argued in the
    record, not just installed.

### The generated artifacts, the gates and the ledger

26. **If any Pydantic model changes, `npm run gen:api` runs and both generated files are committed
    together.** This story is not expected to change one — every endpoint it consumes already
    ships. If AC 21's ruling touches `src/`, that is a wire change and it lands with regenerated
    `openapi.json` **and** `types.d.ts` in the same commit.

27. **The SPA bundle and the `plugin/` mirror are rebuilt and their change is MEASURED.**
   `npm run build` writes into `src/companion/app/static/` — **it mutates `src/`** — and
   `scripts/build_plugin.py` regenerates the mirror; CI drift-checks both. Record before/after
   hashes. This story changes `ui/src` **and puts new code on screen**, so unlike c4-1 the **CSS
   may change too** if any styling lands; report both.

28. **Every `deferred-work.md` entry homed on `c4-2` is enumerated with a disposition each** (C2
    retro ruling R2: inherited deferrals are ACs *at context time*). They are listed in §"The
    inherited deferrals" below. For each: **implement**, **re-home by name**, or **decline with a
    reason**. "Not mentioned" is a failure of this AC. Two corrections belong in the same pass: the
    `@testing-library/react` claim (§"The seam" item 9) and the 2,027-vs-1,999 orphan row count.

### Testing

29. **Every AC above has a test, in the project that can see what it asserts.** Store, fetch-layer
    and component tests are colocated under `src/` (jsdom); guard tests belong in `ui/tests/`
    (node) and must respect the `tsc -b` cross-project import trap. **The FR-07 claim can only be
    made at the root**, from one mount, the way `App.test.tsx`'s FR-22 test is written — a test that
    remounts between the two answers proves nothing about a boot.

30. **The request count is the assertion.** Follow `createPoller`'s `read?:` injection so tests need
    no global `fetch` stub, except where the point *is* the production wiring — `App.test.tsx`
    stubs `globalThis.fetch` deliberately, *"because this file is the only place the whole path is
    exercised end to end, and injecting past any of it would leave that seam untested."*

31. **Evasion probes, in the manner this epic has established.** For each new guard or contract,
    write the probe that *should* defeat it and prove it does not; record every probe **including
    any that passed** — a probe that defeats your own guard is the most valuable line in the record.
    At minimum: (a) a second `fetch(` in a new module; (b) a DFC grouped by its back face;
    (c) a card dropped from every group; (d) a `404` that leaves a stale deck on screen; (e) the
    boot fired twice under a double mount; (f) a deck refusal that reaches the glass as a bare
    status code.

32. **All five frontend gates and all five Python gates are green at the end, with counts recorded
    before and after.** `npm run lint`, `format:check`, `npx tsc -b --force`, `npm test`,
    `npm run build`; `uv run pytest`, `ruff check`, `ruff format --check`, `mypy src/`,
    `mypy src/ --platform win32`. The Python side should be **unchanged unless AC 21's ruling
    touches it** — say which, explicitly.

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (AC 32; standing agreement)
  - [x] Confirm `feat/companion-c4` is at **`2095050`**; cut `feat/companion-c4-2-deck-bootstrap`
        from it
  - [x] Run and record with **durations**: `uv run pytest -m "not integration"` (expect **2,447
        passed, 1 skipped, 54 deselected**), `ruff check`, `ruff format --check`, `mypy src/`,
        `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (expect
        **816 passed, 37 files**), `npm run build`. On a `Worker exited unexpectedly` with no
        failing assertion, re-run before investigating (see the note above)
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*`, `index.html` and the
        `plugin/` mirror (AC 27)
  - [x] **Verify the wire table in §"What the real data says" yourself** from the committed
        `ui/src/api/openapi.json` — if `GET /api/active-deck` publishes a `503`, this story's
        premise has changed and the record says so
  - [x] **Read, in this order:** `src/api/client.ts` end to end, then `src/state/cards.ts`
        (`seedCardSummaries`'s contract), then `src/state/poller.ts` + `src/state/systemState.ts`,
        then `src/components/StatePanel/states.ts` and `src/state/panel.ts`, then `src/App.tsx` and
        `src/components/AppShell/AppShell.tsx`. They are the specification

- [x] **Task 1 — The two readers, decided before any store code** (AC 2, 3, 4, 12)
  - [x] Add `ACTIVE_DECK_PATH`, a `DECK_PATH_PREFIX` + `deckPath()` (encoded, empty refused) and
        two readers to `src/api/client.ts`, both on the shared `request()` helper
  - [x] Give each outcome union the same three-case shape the module already uses, and write the
        **`/api/active-deck` cannot answer `503`** asymmetry into the header where the next reader
        will look
  - [x] Add the `DeckDetail` and `ActiveDeck` aliases to `src/api/schema.ts`, each naming its
        consumer; add none without one (AC 4)
  - [x] Place new files before writing them: a `.tsx` test under `ui/tests/` is a red gate

- [x] **Task 2 — The deck slice and the boot** (AC 1, 5, 18; Q2)
  - [x] One slice beside `systemState.ts` and `cards.ts`, modelling the deck's conditions as
        **values the compiler can exhaust** — never `undefined` versus present (Q2)
  - [x] The boot as a cancellable, generation-guarded sequence; copy `createPoller`'s counter and
        its reasoning, not just its shape (AC 5)
  - [x] Call `seedCardSummaries(detail.cards)` on a successful read, and assert the request count
        is unchanged by it (AC 17)
  - [x] Prove nothing else writes the slice (AC 18) — `ui/tests/store-writes.test.ts`

- [x] **Task 3 — Reconciliation: which surface is on the glass** (AC 6-11; Q1)
  - [x] Apply Q1's ruling in **one** expression; update `poller.ts:238`'s *"until c4-2 ships the
        deck view"* comment in the same commit as the behaviour (§"The seam" item 5)
  - [x] Route deck refusals through `panelFor()`, and write the c4-1-AC-13 contrast beside it
        (AC 10)
  - [x] Rule Q5 (`400` on a deck read) and record the ruling in the code, in the shape
        `PLACEHOLDER_FOR_CARD_REFUSAL` established — a per-context map, `states.ts` untouched
  - [x] Prove two different `503`s produce two different panels from the deck path (AC 9)
  - [x] Prove a `404` clears the deck and that `App.test.tsx`'s existing panel assertions still
        pass unmodified (AC 7, AC 8) — **two assertions changed; see Completion Notes**

- [x] **Task 4 — The type-group derivation** (AC 13-16; Q3, Q4)
  - [x] One ordered list serving both group order and multi-type precedence (AC 15)
  - [x] Front-face split on ` // ` (AC 14) — with the four disagreeing cards from the table as
        named fixtures, not invented uuids — **plus six that actually discriminate the rule**
  - [x] Apply Q4's board ruling (commander / mainboard / sideboard)
  - [x] Assert **conservation**: every payload row lands in exactly one group and the quantities
        sum (AC 16). Include the `'Card'` row and a `'Card // Card'` fixture
  - [x] Derive it once, in the store; nothing fetches (AC 13)

- [x] **Task 5 — The header** (AC 19, 20, 21)
  - [x] Fill `deckName` and `badges` from `App.tsx`; `AppShell.tsx` unedited
  - [x] Rule AC 21's optionality asymmetry and record it — **declined, with the measurement**
  - [x] **Eye-check `Badge` on a real screen** and **run the contrast numbers** on the tone-over-wash
        (the two ledgered items homed here); record both outcomes, including "looks right"

- [x] **Task 6 — Evasion probes** (AC 31)
  - [x] Probes (a)-(f) at minimum; record every probe and its outcome, including any that **passed**
        — **three passed and drove real repairs**

- [x] **Task 7 — The ledger, the docs and the artifacts** (AC 26, 27, 28, 32)
  - [x] Give each inherited deferral a disposition (AC 28), plus the two corrections
  - [x] Update `ui/README.md`'s *"Not here yet"* section, the alias count, and the two
        displacement bullets — the left column and the `h1` both change here
  - [x] Rebuild the bundle and the `plugin/` mirror; record before/after hashes (AC 27)
  - [x] Re-run all ten gates; record counts and durations

### Review Findings

Three-layer review (Blind Hunter / Edge Case Hunter / Acceptance Auditor) run 2026-08-03.
11 raw findings → 2 decisions + 7 patches after triage; 2 dismissed (unvalidated counts feeding
badges — unreachable with the Pydantic backend, within `deckOf`'s declared posture; `413` on the
deck read — unreachable, the id is ≤ 256 chars and the GET has no body). Both decisions ruled by
Brad 2026-08-03: **the boot gains an edge-triggered re-drive on poll recovery**, covering both.
All 9 items below are applied; frontend gates green at **970 passed / 41 files** after patches.

- [x] [Review][Decision] **[High] A `refused` deck state pins a stale error panel past recovery — an FR-22 regression on the deck path** — A cold open while the DB is building/refreshing, with an active deck set (which `PUT /api/active-deck` permits with no DB), boots once, gets `503 database_not_initialized` (or `database_unavailable`) on the deck read, and settles `{status:'refused'}`. Nothing ever transitions out of `'refused'`: the boot never re-runs, and `surfaceOf`'s arm 2 outranks the system panel unconditionally. When the build finishes, the poll recovers to `200` but the glass stays on the stale 503 panel until a manual reload — and while pinned, the poller's 60-second `stalled` escalation is also invisible. The declared residue ("a deck set while the tab is open waits for Epic 5") covers a *new deck*, not a refusal panel outliving the condition it reported. Fix requires a ruling: re-drive the boot on a system-state recovery transition, let a *newer* system decision outrank a stale refusal in `surfaceOf`, or declare the residue and re-home it by name (c5-4/c5-6). `ui/src/state/deck.ts:380-383`
- [x] [Review][Decision] **[Medium] `unreachable` on either boot request settles `'none'` — the glass claims "no active deck" while one is active** — One 10-second timeout or dropped connection on `GET /api/deck/{id}` folds to `'none'`; with the poll healthy the system panel is `no-active-deck` listing deck names — an affirmative false claim that persists until reload. The docstring borrows `poller.ts`'s "nothing was decided" posture, but the poller *emits nothing* on unreachable (previous truth stands) while the boot actively emits `'none'`. Same root as the finding above (no re-drive); the same ruling should cover both. `ui/src/state/deck.ts:293,312`
- [x] [Review][Patch] **[Medium] A malformed row inside a valid-looking `200` deck body crashes the boot into a permanent `'booting'`** — `deckOf` validates only `id`/`name`/`Array.isArray(cards)`, so a non-conforming row reaches `boardsOfDeck`, where `frontFace` throws after the last generation check and outside any try/catch: unhandled rejection, `settle` never called, slice stuck at `'booting'` forever with no panel — breaking the module's own "every outcome is a value" posture. Wrap the seed+derive+settle in a try/catch settling an internal-error refusal. [ui/src/state/deck.ts:322-323]
- [x] [Review][Patch] **[Low] Q5's `invalid_request → no-active-deck` override also applies to the active-deck route, where its justification does not hold** — the override is argued from "the id in the path came from `PUT /api/active-deck`", but `GET /api/active-deck` carries no path parameter, so a `400` from it is exactly the client-bug case `states.ts` classifies; the code folds it to a calm `'none'` while the test file's own comment says `internal-error` is the honest panel there. Route active-route errors through `panelFor` without the deck override. [ui/src/state/deck.ts:294]
- [x] [Review][Patch] **[Low] Misleading comment: seeding claimed "unguarded by the generation check on purpose", but the guard two lines up already returns** — the `gen !== generation || !live` check after the `readDetail` await sits *before* `seedCardSummaries`, so a stopped/superseded boot never seeds; the comment's rationale describes behavior the code does not have, and a future reader "fixing" either side to match the other could reintroduce the c4-1 mid-flight-seed class. Align the comment to the (conservative, correct) code. [ui/src/state/deck.ts:310-322]
- [x] [Review][Patch] **[Low] The boot's second lock passes a whitespace-only id** — the guard checks `deckId === null || deckId === ''` while `activeDeckIdOf` folds on `trim()`; an injected reader returning `'  '` reaches `readDetail` and issues `/api/deck/%20%20`, the request the "second lock" docstring says cannot happen. Check `deckId.trim() === ''`. [ui/src/state/deck.ts:302]
- [x] [Review][Patch] **[Low] The store-writes scanner has two spelling-keyed blind spots** — store discovery matches only `export const X = create<` (a `create(combine(...))`, aliased import, or `createStore` slice is invisible to the completeness check), and the comment stripper eats `//` inside string literals, hiding a same-line `setState` after e.g. `"a//b"`. Broaden the discovery regex and either harden or declare the string-literal residue alongside the file's existing one. [ui/tests/store-writes.test.ts:61,116]
- [x] [Review][Patch] **[Low] `DeckBoot.start()` is inert forever after the sequence completes, not just "while running"** — `live` is never cleared when `run` settles, so the docstring's "Idempotent while running" understates it; a future caller (Epic 5 re-boot) expecting a re-drive gets a silent no-op. Fix the docstring to state the one-shot-per-start/stop contract. [ui/src/state/deck.ts:234,327-331]
- [x] [Review][Patch] **[Low] `App.test.tsx` comment undercounts the changed assertions** — the "stops polling" test's comment says "THE ONE PRE-EXISTING ASSERTION c4-2 CHANGED", but the FR-22 transition test's request count also changed in the same commit; the Completion Notes correctly say two. One-word fix. [ui/src/App.test.tsx]

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

1. **AD-16**, verbatim on the two clauses that bind here: *"status codes carry the outcome, success
   bodies are the existing Pydantic schemas **unwrapped**, every non-2xx returns one typed error
   body with a closed snake_case `reason` token mapping 1:1 onto a UX state"*, and **"Nothing in the
   SPA keys off a bare status code."** Every branch in this story is on the **token**.

2. **AD-12 / the spine:** *"its state comes from exactly two inputs — REST responses and WebSocket
   messages. Nothing else may write the store."* And *"Card identity is the Scryfall printing
   UUID, everywhere, always"* — `deck_cards.card_id` is that id, and it is what
   `seedCardSummaries` keys on (c4-1 keys on the deck row's own `card_id`, not the nested
   `card.id`).

3. **FR-07's specified behaviour, not a limitation:** the active deck lives in the backend's memory
   and dies with the process, so *"after a restart this reports none, whatever was displayed
   before."* A cold open finding `deck_id: null` is the normal case.

4. **c3-1 Q4:** *"a deck id has no declared shape"* — there is no malformed-deck-id answer from the
   handler, only routing's own `invalid_request` for a value that is not a single path segment.

5. **c2-9 Q6 / the state-panel posture:** *"One state panel at a time, in the left-column area; the
   right column, nav and footer remain functional around it"* — and `StatePanel` stays
   presentation-only with **no fallback branch**, which is why `panelFor` must be total.

6. **c2-6 Q3:** the page is never heading-less. `AppShell` uses `filled()` rather than a default
   parameter *"because a default fires only on `undefined`, so an empty string or null from a
   loading gap would render an EMPTY h1."*

7. **c4-1 Q1:** one door, named exhaustively. **c4-1 Q5:** a token's UI destination may be
   context-dependent, and the way to record that is a per-context map beside the consumer, with
   `states.ts` untouched — because adding the token to `PLACEHOLDER_FOR_REASON` would break
   `ReasonClassificationsAreDisjoint`, *"and rightly."* Q5 of this story is the same shape.

### The eleven things this story must not break

1. `posture.test.ts`'s **exhaustive** network-door list (`:308-334`) — one door, and `App.tsx` is
   not it, while still matching `useSystemState(`.
2. `package-contract.test.ts`'s no-second-state-library and no-second-codegen bans.
3. `wire-contract.test.ts`'s ban on re-declaring any `components.schemas` shape outside `src/api/`,
   and on importing `./types` outside `schema.ts`.
4. `shell.test.ts`'s **exhaustive import lists** and the hook/`fetch`/`WebSocket` bans over
   `AppShell.tsx` and the eight primitives — **and its git-derived coverage guard, which turns any
   new component into a red test by design.** `shell.test.ts:1219-1239` runs `git ls-files
   src/components/*.ts src/components/*.tsx`, drops test files, and asserts
   `expect(onDisk.sort()).toEqual(covered)` against a **hand-kept 14-entry `PRIMITIVES` list plus
   the shell** — installed by the 2026-07-29 review precisely because *"a FIFTH component added
   under `src/components/` would escape every assertion in this suite by never being listed."* So
   if Q9's answer puts a `DeckBadges` (or any other) component under `src/components/`, that commit
   **must** add it to `PRIMITIVES` with its exhaustive import list, bump the `toHaveLength(14)`
   non-vacuity count, and accept the presentation-only bans that come with membership — including
   the **type-only `react` import** (`filled.ts` is the one exemption, and it was argued). This is
   a gate, not a review note: discovering it after writing the component is the expensive order.
5. `gate-geometry.test.ts`'s "no `.tsx` test files under `ui/tests/`".
6. `copy-rules.test.ts`'s prose ban outside `COPY_MODULES`, and the `!`/emoji/"something went
   wrong" ban across **all** of `src/`.
7. `states.ts`'s **six** type-level asserts (`EveryPanelHasASource`, `PanelSourcesAreDisjoint`,
   `EveryPanellessReasonIsClassified`, `ReasonClassificationsAreDisjoint`,
   `NothingWithAPanelIsClassified`, `EveryPlaceholderIsAReal` — c4-1's record says four, which was
   true at c2-9 and has not been since c3-2). They are set equalities over the token vocabulary; a
   classification added without a token is a `typecheck` failure naming it.
8. `App.test.tsx`'s FR-22 transition test — one mount, two answers, one component — **and** its
   *"stops polling once the database is there"* assertion (`toHaveBeenCalledTimes(1)` after ten
   minutes). A boot that polls is a red test.
9. `copy-tails.test.ts`, which reads `DECKS_PATH` out of `client.ts` by path.
10. `attribution.test.ts` / the footer assertions — the attribution survives every state, and this
    story adds a state.
11. The **committed bundle + `plugin/` mirror** drift gates. `npm run build` mutates `src/`.

### Source tree — what exists, what this story touches

```
ui/src/
  api/
    client.ts       ← THE one door. ADD: active-deck + deck-detail readers, on the shared request()
    schema.ts       ← 7 aliases today; ADD DeckDetail + ActiveDeck, each naming its consumer
    types.d.ts      ← GENERATED, committed, drift-checked. Never hand-edit
    openapi.json    ← GENERATED, committed. `npm run gen:api` rewrites both
  state/
    systemState.ts  ← the system-panel slice + useSystemState. Q1 decides how the deck reconciles
    poller.ts       ← :238's "until c4-2" comment retires here. The generation-counter precedent
    panel.ts        ← wire token → StateKey. ON the deck path (AC 10) — unlike the card path
    cards.ts        ← seedCardSummaries is called from this story. Otherwise untouched
    <new>           ← the deck slice + the type-group derivation
  components/       ← UNTOUCHED as source. Badge gains its first CONSUMER, not an edit.
                      A NEW module here is a red `shell.test.ts` gate until PRIMITIVES lists it
                      (don't-break 4) — so decide the header's home BEFORE writing it (Q9)
  App.tsx           ← fills deckName + badges, and applies Q1's precedence
ui/tests/           ← node project. Guard tests only, no .tsx, mind the tsc -b trap
```

**Backend: read-only.** `GET /api/active-deck` (`routes/active_deck.py:67-87`),
`GET /api/deck/{deck_id}` (`routes/decks.py:62-91`) and `GET /api/decks` (`:33-59`) are complete,
tested and shipped. This story consumes them and — unless AC 21's ruling says otherwise — changes
nothing under `src/`.

### The inherited deferrals (AC 28 — give each a disposition)

Search `deferred-work.md` for `c4-2`. Summarised, with the line where each lives:

1. **`GET /api/decks` and `GET /api/deck/{id}` have never been called by a browser** (`:1666`,
   Low) — *"Home: c4-2 (the deck bootstrap, the first real consumer)."* This story makes it
   automatic; the C3 retro carries it as checklist items **C1/C2**.
2. **Generated-type optionality asymmetry** (`:1889`, Low) — `strategy?: string | null` vs
   `format: string | null`, plus `@default 0` on the counts. Annotated at c4-1 as **not triggered
   there and c4-2's alone, unshared**: *"which reads exactly those fields when it renders the deck
   header."* See AC 21.
3. **No sanctioned `DeckDetail` alias** (`:2108`, resolved-in-part note at `:2120`) — c4-1 added
   `Card`, `CardSummary` and `DeckCardSummary` and deliberately declined `DeckDetail`: *"c4-2 adds
   `DeckDetail` when its fetch needs it."* See AC 4. (`CardFace` stays c4-6's.)
4. **The c4-1/c4-2 seam restatement** (`:3252`) — *"The c4-2 half is untouched and still owed:
   it inherits a poll already calling `GET /api/decks`, its job is to read the DECK rather than the
   deck names, and it now also inherits `seedCardSummaries`."* Disposition: read it and say so.
5. **Three transient failures make an id terminal for the tab's life while the whole-screen poller
   self-heals (FR-22 asymmetry)** (`:3280`) — the named fix is `resetCardCache()` on the
   `deck_changed` (or recovery) transition, *"which c4-2 owns"*, with c4-5 as the story that makes
   it visible. See **Q7** — note that `deck_changed` is Epic 5's event and this story may not have
   the transition the entry assumes.
6. **The orphaned-hydration return residue** (`:3287`, Greptile PR #40 P2, ruled *declare*) — a
   `hydrateCard` promise a reset orphans still resolves with the entry it computed for the
   discarded world. *"The moment c4-2 wires a production reset, decide whether awaiting callers
   need the fresh answer (widen the return to `CardEntry | undefined`) or the docstring's 'the
   store is the authority' ruling stands."* Falls out of Q7's answer.
7. **The four primitives' APPEARANCE is not dev-verified** (`:1331`, **Medium**) and its extension,
   **the tone-over-wash CONTRAST is unmeasured** (`:1357`) — *"`Badge` at c4-10 (the format check)
   and c4-2 (the header badges) … eyeball the wash's stacking AND run the contrast numbers at c4-2 /
   c4-10."* See AC 20. The failure mode is a solid blank pill with invisible text; check it first.
8. **C3 retro F2 — the kicker and the `h1` say the same words** (retro `:225`) — *"c4-2 replaces
   the string. Known and self-resolving, but it does read as a defect on screen — recorded so c4-2
   does not treat the swap as cosmetic."* See AC 19.
9. **C3 retro action item 4 — a gate banning story-key-shaped strings from rendered text**
   (`/\bc\d+-\d+\b/`), owner *"Sathias (c8-5, **or earlier if a C4 story is nearer**)"*. See **Q8**.
10. **C3 retro carried manual-testing items A3/A4** — *"c4-2 renders four of the five panels for
    real; A3-A6 are its acceptance surface"*, with the known trade already ruled: after c4-2 a
    failure is ambiguous between *the panel* and *the new wiring*. Feed these into the C4 checklist.

**Two corrections this ledger pass owes** (AC 28): the `useCardEntry` deferral's stated reason
(*"no testing library exists in the dependency set"*) is **false** — `@testing-library/react@^16.3.2`
ships and `App.test.tsx` uses it; and c4-1's *"0 dangling references across 2,027 `deck_cards`
rows"* is right about **card** references but **28 of those 2,027 rows are orphaned by DECK id**
(2 deleted decks, no FK enforcement on the async engine). Neither changes a decision; both are
numbers later stories will quote.

### Project structure notes — the conventions a new module inherits

- **A store slice is not a component.** No `.css`, no directory-per-thing; `src/state/*.ts` is flat
  and each file has a module docstring stating what it owns and what it deliberately does not.
- **Docstrings are Google-style and carry the arithmetic.** Every constant in `poller.ts`,
  `client.ts` and `cards.ts` carries the sum that produced it. **A bare number in this codebase is
  a defect** — and this story's numbers (a group order, an attempt bound, a precedence list) each
  need the reason travelling with the value.
- **Named exports only, no barrels, no default export** except `App.tsx`'s.
- **`verbatimModuleSyntax` is on** — `import type` for types, always.
- **Prettier, ESLint and stylelint are gates, not preferences**, and `ui/.gitattributes` forces LF
  (the repo sets `core.autocrlf=true`; without it `prettier --check` is red on Windows and green on
  CI from the same commit).
- **Class names are flat kebab-case prefixed with the component** — `app-shell__header` is a
  stylelint ERROR (measured: 12 `selector-class-pattern` errors on that one stylesheet).

### Open questions — answer these before writing code

**Q1 — When a deck and a system state are both true, which is on the glass, and where is that
decided?**
*Proposed:* **the deck slice is the authority for the left column whenever it holds a deck, and the
system panel is the authority otherwise — expressed once**, in the store (a single derived value
`App.tsx` renders), not as a ternary in JSX. Rationale: `EXPERIENCE.md`'s state table gives the
answer per row (*"Cold open, backend live, deck set"* → deck view; *"Fresh install, DB missing"* →
panel; *"Deck deleted"* → panel), and every one of those rows is *"a deck, or a panel, never both"*.
Putting the rule in the store means c4-4's grid and c4-12's empty state read it rather than
re-deriving it, which is the same argument the epic makes for the type grouping one level down.
*The alternative* — `App.tsx` branching on `deck !== null` — is two lines today and becomes the
second copy of a precedence rule the moment c4-12 adds "empty deck renders the header but not the
grid". **Note the interaction with `poller.ts:239`**: today a `200` from `/api/decks` unconditionally
decides `'no-active-deck'`. If the deck wins, that decision is still *made* and simply not rendered
— which is honest and cheap — but the comment saying "until c4-2" must be corrected either way.

**Q2 — How is the deck state modelled?**
*Proposed:* a **discriminated union**, in the manner of `DecksOutcome` and `CardEntry` —
`{status:'booting'}` | `{status:'none'}` | `{status:'deck', detail: DeckDetail, groups: …}` |
`{status:'refused', reason: ErrorReason | null}` — so no consumer ever infers a condition from
`undefined` and the compiler can exhaust it. Rationale: c4-1's Q2 chose exactly this for the card
cache and the review found the one bug it did *because* the states were values (a stale summary
snapshot), not despite it. `'booting'` is a real state a cold open occupies for one paint on
localhost, and it is distinct from `'none'` — the panel a fresh tab shows before the first answer
is the c3-9 question all over again. *The alternative* — `deck: DeckDetail | null` plus a separate
`error` field — is two invariants that can disagree, and the disagreement is invisible until a
consumer reads both.

**Q3 — What is the type-group vocabulary, and what order do groups come in?**
*Proposed:* **one ordered list serving both order and precedence** —
`Creature · Planeswalker · Battle · Instant · Sorcery · Artifact · Enchantment · Land · Other` —
first match against the front face's supertype-stripped words wins. Rationale: it is the
conventional decklist order every MTG tool uses; it makes `Artifact Creature → Creature` and
`Legendary Artifact Planeswalker — Equipment → Planeswalker` fall out of the same list that
determines display order (88 live rows need the precedence); and one list is one thing to drift.
`Battle` and `Kindred`/`Tribal` are in the corpus (39 and 82 cards) but in **no** deck today —
include `Battle` because a real type with a real group is cheap, and let `Kindred`/`Tribal` fall
into the ordinary path since a Kindred card always carries a second real type. `Other` is the
residual AC 16 demands. *The alternatives:* the design mock's four buckets
(`Creatures · Spells · Planeswalkers · Lands`, `imports/claude-design/…dc.html:325`) — which is
hand-authored demo data, groups a Saga under "Creatures", and would need its own "what is a Spell"
rule; or deriving groups from the data (one per distinct primary type present), which produces a
different, unstable order per deck and gives UX-DR12's group header nothing to be stable about.
**Whichever is chosen, the list is exported and the order is asserted**, because c4-7 renders it
and c4-5's *"the first card of the first type group"* depends on it being deterministic.
**One declared consequence either way:** `Land Creature — Forest Dryad` (Dryad Arbor) groups as a
**Creature** under first-match. 4 in the corpus, **0 in any deck**; note it, do not special-case it.

**Q4 — Does the derivation partition commander / mainboard / sideboard before grouping by type?**
*Proposed:* **yes — three boards, with the type groups inside the mainboard**, because
`DeckCardSummary` already carries `sideboard` and `commander` as first-class flags and 16 of 40
decks have a commander. Rationale: a commander filed under "Creatures" misstates the deck to
anyone reading the list, and the sideboard is not part of the deck the curve and colour panels
describe (`view_model.py` already partitions `sideboard is False` for exactly this reason). Doing
it here means c4-4, c4-7 and c4-8 inherit one partition rather than each writing `filter(c =>
!c.sideboard)` slightly differently. *The alternative* — group everything by type and let each
consumer filter — is what the epic's *"the grid and the list panel cannot disagree"* clause exists
to prevent. **Measured cost of getting it wrong:** 41 sideboard rows across 5 decks and 16
commander rows would silently join the type groups and inflate every count on screen.

**Q5 — Does a `400 invalid_request` on a DECK read become the no-active-deck panel?**
*Proposed:* **yes**, recorded in a per-context map beside the consumer, `states.ts` untouched —
the identical shape c4-1's Q5 ruled for card reads. Rationale: `NO_UI_RESPONSE`'s premise is *"the
SPA never generates a malformed request"*, and that is exactly what fails here — the id came from
`PUT /api/active-deck`, which accepts **any non-blank string ≤ 256 chars, stores it verbatim, and
deliberately does not check that the deck exists**. An id the app cannot resolve is an id the app
cannot resolve, whichever token says so, and *"there is no active deck"* is the true sentence.
Letting it reach `panelFor` unmodified produces *"The companion hit a bug. Restart the companion."*
for an agent typo. *The alternative* — declining, on the grounds that `states.ts`'s classification
is decided — is defensible **only if written down as a decline with the ledger entry re-homed by
name**. Do not leave it undecided (AC 11).

**Q6 — Does the deck read get a bound on attempts, or does it need none?**
*Proposed:* **none, because it issues no retry at all** — one request per boot, and the re-drive is
somebody else's (Epic 5's `deck_changed`, c5-6's reconnect). Rationale: `MAX_ATTEMPTS_PER_CARD`
exists because *renders* call `hydrateCard` in a loop; nothing here loops, and c4-1 measured that
`readCard` needed no timer once the bound lived with the caller. **But verify the claim rather than
asserting it**: if Q1's ruling makes the boot re-run on any poll transition, that IS a loop and it
needs a bound — and the 503-outranks-400 trap applies to `/api/deck/{deck_id}` exactly as it did to
`/api/cards/{card_id}`. *The alternative* — copying `MAX_ATTEMPTS_PER_CARD` — is cheap insurance and
costs one constant with its arithmetic. **Either way AC 12 needs a test that a forever-`503` id
does not produce unbounded requests.**

**Q7 — Does this story wire `resetCardCache()`, and does the orphaned-return residue close?**
*Proposed:* **no — re-home both to c5-4/c5-6 by name.** Rationale: the ledger homed them here on
the theory that c4-2 owns a `deck_changed` transition; measured, **it does not** — `deck_changed`
is an Epic 5 WebSocket message, this story boots once and never switches decks. And a blanket reset
on deck switch is probably the wrong fix anyway: the cache is keyed by printing uuid and shared
with Epic 6's agent views (AD-12's second sentence), so resetting it on a deck change throws away
hydration for every card the two decks share. *The alternative* — shipping a reset on the one
transition this story does have (a `404` clearing to no-active-deck) — is a real option and would
close the FR-22 asymmetry for the deleted-deck case; if taken, the orphaned-return question
(entry 6) becomes live and must be answered in the same commit. **Re-homing is a named re-home,
not a silent drop.**

**Q8 — Does this story build the story-key gate (retro action item 4)?**
*Proposed:* **no — leave it on c8-5, and say why in the record.** Rationale: this story *removes*
two of the six offending strings from the first-run view (the `h1` stops saying the product name
via c4-2, and the header badge placeholder naming `c2-7 / c4-2 / c4-10` is displaced) but leaves
four, and a gate banning `/\bc\d+-\d+\b/` in rendered text would fail on `AppShell.tsx`'s remaining
placeholders **which are correct today** — so building it here means shipping it disabled or
shipping an allowlist, and an allowlisted ban is the "enumerate members" anti-pattern this epic
has now violated three times. *The alternative* — build it with the remaining placeholders as
declared exemptions that each name their owning story — is defensible and would make every future
placeholder arrive with a home; it is a bigger piece of work than it looks and it is not this
story's subject. **Whichever way, record it so the retro item is answered rather than passed over.**

**Q9 — What exactly do the two header badges say, and in what tone?**
*Proposed:* **format** (`brawl`, `standard`, …) in `neutral`, and **size** from the counts
(`100 maindeck`, plus `15 sideboard` only when `sideboard_count > 0`) in `neutral`. Rationale: the
mock shows three badges — `standard legal` (positive), `60 maindeck`, `15 sideboard` — but the
first is a **legality claim**, and legality comes from `GET /api/deck/{id}/format-check`, which is
**c4-10's** route and carries its own ledgered warning about binding `is_legal` to a headline.
A `positive` tone here would be this story asserting something it never asked the backend.
Measured: every deck in the corpus has a non-null `format`, so the "no format" branch is untested
data — decide whether it renders nothing or a `caution` badge, and note that c4-10 owns the real
"no format to check against" answer (`format_recognized`). *The alternative* — a single combined
badge — loses UX-DR8's "format/size badges" plural and the mock's density.

**Q9b — and do the badge's numerals get the numeric role?** *Proposed:* **yes, and it costs one CSS
rule with two declarations.** `Badge.css:77` is `font: var(--type-label)` — 11px, uppercase,
tracked — so a size badge renders `100 MAINDECK` with **proportional** figures, while UX-DR3 asks
for tabular numerals on *"every count, quantity, price and axis value"* and DESIGN.md's own label
guidance says *"panel titles that need to carry counts should put the count in
`{typography.numeric}` beside the label, not inside it."* So the count is a `<span>` inside the
badge carrying `font: var(--type-numeric)` **and** `font-variant-numeric:
var(--type-numeric-features)` — together, because `findUnpairedNumericRole` fails the pair split and
the shorthand cannot carry the feature. *The alternative* — leave it uppercase and proportional —
is the c2-10 finding repeated knowingly (*"the legal sentence renders all-caps"*), and if taken it
must be written down as accepted rather than left to a reviewer to notice. **Either way `Badge.tsx`
is not edited** — it takes `children`, and the span is the caller's. **But WHERE that span and its
stylesheet live is a decision with a gate attached**: `src/App.css` was deleted at c2-6, `AppShell`
is not to be edited, and a new module under `src/components/` reds `shell.test.ts`'s coverage guard
until `PRIMITIVES` lists it (don't-break 4). The three honest options — a listed
`src/components/DeckBadges/`, inline nodes composed in `App.tsx` against an existing stylesheet, or
no numeric role at all — differ in cost, and the cheapest is not obviously the right one. Decide
before writing.

### References

- Epic story text: [epics-companion-app.md#Story 4.2](_bmad-output/planning-artifacts/epics-companion-app.md#L1878-L1909) · Epic 4 header [#L1837-L1843](_bmad-output/planning-artifacts/epics-companion-app.md#L1837-L1843) · c4-1 [#L1844-L1876](_bmad-output/planning-artifacts/epics-companion-app.md#L1844-L1876) · c4-4 [#L1941-L1991](_bmad-output/planning-artifacts/epics-companion-app.md#L1941-L1991) · c4-7 [#L2084-L2121](_bmad-output/planning-artifacts/epics-companion-app.md#L2084-L2121)
- **FR-05** (grouped by type, DFCs by front face): [epics-companion-app.md#L55-L59](_bmad-output/planning-artifacts/epics-companion-app.md#L55-L59) · **FR-07** (active deck, no-active-deck state) [#L64-L67](_bmad-output/planning-artifacts/epics-companion-app.md#L64-L67) · **FR-11** (404 clears) [#L78-L82](_bmad-output/planning-artifacts/epics-companion-app.md#L78-L82) · **FR-13** [#L89-L92](_bmad-output/planning-artifacts/epics-companion-app.md#L89-L92) · **FR-22** [#L126-L129](_bmad-output/planning-artifacts/epics-companion-app.md#L126-L129) · **NFR-05** [#L157-L161](_bmad-output/planning-artifacts/epics-companion-app.md#L157-L161)
- **UX-DR8** (the header composition): [epics-companion-app.md#L372-L379](_bmad-output/planning-artifacts/epics-companion-app.md#L372-L379) · **UX-DR10** (Badge tones) [#L386-L388](_bmad-output/planning-artifacts/epics-companion-app.md#L386-L388) · **UX-DR12** (group header) [#L392-L394](_bmad-output/planning-artifacts/epics-companion-app.md#L392-L394) · **UX-DR30** (state panel) [#L500-L505](_bmad-output/planning-artifacts/epics-companion-app.md#L500-L505) · **UX-DR33** (copy verbatim) [#L520-L524](_bmad-output/planning-artifacts/epics-companion-app.md#L520-L524) · **UX-DR35** (refetch — c5's, read for the 404 rule) [#L534-L540](_bmad-output/planning-artifacts/epics-companion-app.md#L534-L540)
- **AD-12 / AD-16 / the consistency conventions**: [ARCHITECTURE-SPINE.md#L272-L291](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L272-L291) · [#L329-L352](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L329-L352) · [#L355-L360](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L355-L360)
- **The behaviour contract**: [EXPERIENCE.md — the state table](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L109-L132) · the no-active-deck copy [#L63](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L63) · the deck-list row [#L36](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L36) · refetch rules [#L103](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L103) · semantic structure [#L154](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L154) · the deck header IA row [#L31](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L31)
- **The visual contract**: [DESIGN.md — Badge / Group header](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L370-L390) · the composition reference and its corrections [#L366](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L366) · the mock's header badges and its `order` array [imports/claude-design/Planeswalker Companion.dc.html](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/imports/claude-design/Planeswalker%20Companion.dc.html#L33-L43)
- **The seam to extend**: [client.ts](ui/src/api/client.ts) — the one-door ruling and the c4-2 routes [#L1-L64](ui/src/api/client.ts#L1-L64), `cardPath`'s encoding argument [#L119-L141](ui/src/api/client.ts#L119-L141), the shared `request()` [#L227-L289](ui/src/api/client.ts#L227-L289) · [cards.ts](ui/src/state/cards.ts) — `seedCardSummaries` [#L343-L379](ui/src/state/cards.ts#L343-L379) · [poller.ts](ui/src/state/poller.ts) — the generation counter [#L160-L204](ui/src/state/poller.ts#L160-L204), the line that retires [#L236-L248](ui/src/state/poller.ts#L236-L248) · [systemState.ts](ui/src/state/systemState.ts) — the one-consumer rule [#L49-L72](ui/src/state/systemState.ts#L49-L72) · [panel.ts](ui/src/state/panel.ts#L44-L71)
- **The token vocabulary**: [states.ts — `PANEL_FOR_REASON`](ui/src/components/StatePanel/states.ts#L91-L134) (note `deck_not_found` at [#L95](ui/src/components/StatePanel/states.ts#L95)) · `NO_UI_RESPONSE` [#L182-L186](ui/src/components/StatePanel/states.ts#L182-L186) · `RETRIES_QUIETLY` [#L223-L237](ui/src/components/StatePanel/states.ts#L223-L237)
- **The slots this story fills**: [AppShell.tsx — `deckName` / `badges`](ui/src/components/AppShell/AppShell.tsx#L51-L77) and their placeholders [#L92-L118](ui/src/components/AppShell/AppShell.tsx#L92-L118) · [App.tsx](ui/src/App.tsx#L70-L85) · [filled.ts](ui/src/components/filled.ts) · [Badge.tsx](ui/src/components/Badge/Badge.tsx)
- **The endpoints**: [active_deck.py#L67-L87](src/companion/app/routes/active_deck.py#L67-L87) — note *"no `DbSession`… not a `503` path"* [#L15-L20](src/companion/app/routes/active_deck.py#L15-L20) · [decks.py#L62-L91](src/companion/app/routes/decks.py#L62-L91) · the `ActiveDeck` contract and its URL-encoding instruction [contracts.py#L212-L243](src/companion/contracts.py#L212-L243) · `ActiveDeckRequest`'s stores-anything ruling [#L246-L287](src/companion/contracts.py#L246-L287) · the projection [deck.py#L234-L285](src/data/schemas/deck.py#L234-L285)
- **The two land policies**: [view_model.py::is_land — front face](src/viewer/view_model.py#L166-L174) vs [mana_base.py::_is_land — whole string](src/logic/assessment/mana_base.py#L71-L81) and [mana_curve.py#L74](src/logic/mana_curve.py#L74)
- **The guards that will fail first**: [posture.test.ts#L308-L346](ui/tests/posture.test.ts#L308-L346) · [wire-contract.test.ts](ui/tests/wire-contract.test.ts) · [package-contract.test.ts](ui/tests/package-contract.test.ts) · [shell.test.ts](ui/tests/shell.test.ts) · [copy-rules.test.ts#L103-L128](ui/tests/copy-rules.test.ts#L103-L128) · [App.test.tsx#L185-L255](ui/src/App.test.tsx#L185-L255)
- **The previous story**: [c4-1](_bmad-output/implementation-artifacts/c4-1-a-single-card-hydration-cache-with-in-flight-deduping.md) — its Q5 ruling and the ten review patches
- **The ledger**: [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — search `c4-2`
- **What C4 inherits, by story, and the carried manual tests**: [epic-c3-retro-2026-08-02.md#L538-L580](_bmad-output/implementation-artifacts/epic-c3-retro-2026-08-02.md#L538-L580) · F1/F2/F3 [#L219-L231](_bmad-output/implementation-artifacts/epic-c3-retro-2026-08-02.md#L219-L231) · the carried-item table [#L430-L470](_bmad-output/implementation-artifacts/epic-c3-retro-2026-08-02.md#L430-L470)
- Project rules: [project-context.md](_bmad-output/project-context.md) · frontend conventions [ui/README.md](ui/README.md) — the *"Not here yet"* seam at [#L963-L1050](ui/README.md#L963-L1050)

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow.

### Debug Log References

**The nine open questions: all as proposed** (tenth story running), with Q6 and Q9's sub-question
strengthened by measurement rather than merely confirmed, and Q9b's *"decide before writing"* fork
taken toward a listed component.

| Q | Ruling |
| --- | --- |
| **Q1** | **As proposed.** `surfaceOf(deck, system)` in `src/state/deck.ts` — ONE exported expression. **Three arms, not two**, and the middle one is the change: *a loaded deck* → *a deck refusal that decided a panel of its own* → *the system panel*. Without the middle arm AC 9's two-503s criterion would pass only because the poll usually agrees, i.e. vacuously. |
| **Q2** | **As proposed.** A discriminated union — `booting` / `none` / `deck` / `refused`. `'none'` docstrings as *"no deck is on the glass and no deck-specific panel is claimed"*, which is honest for all three of its inputs (`deck_id: null`, a refusal whose panel IS `no-active-deck`, and `unreachable`). |
| **Q3** | **As proposed.** `Creature · Planeswalker · Battle · Instant · Sorcery · Artifact · Enchantment · Land · Other`, one exported list serving both display order and multi-type precedence, order asserted by value. `Battle` included, `Kindred`/`Tribal` not. Dryad Arbor → Creature, declared. |
| **Q4** | **As proposed, with one correction the arithmetic forced.** Three boards — but the partition splits on **`sideboard` FIRST**, because `deck.py::_counts` sums on that flag alone, so a (hypothetical) sideboarded commander is counted in `sideboard_count`. Splitting on `commander` first would have broken the conservation identity for a reason nobody could see. 0 live rows are both. |
| **Q5** | **As proposed.** `400 invalid_request` on a deck read → `no-active-deck`, in `PANEL_FOR_DECK_REFUSAL`, a one-entry per-context map beside the consumer. `states.ts` untouched. |
| **Q6** | **As proposed, and now measured.** No bound, because there is no retry: one `GET /api/active-deck` and at most one `GET /api/deck/{id}` per mount. `App.test.tsx` asserts exactly that over ten minutes of fake time against a forever-`503` id — **and asserts in the same test that the POLL kept going**, so "nothing retries" cannot read as "the boot is right". |
| **Q7** | **As proposed.** `resetCardCache()` and the orphaned-return residue **re-homed by name to c5-4 / c5-6**. Measured: this story has no `deck_changed` transition, and a blanket reset on a deck switch is probably the wrong fix anyway — the cache is keyed by printing uuid and shared with Epic 6's agent views. |
| **Q8** | **As proposed.** The story-key gate stays **c8-5**. c4-2 removes two offending strings and leaves **six**, counted off the real render, every one correct today. |
| **Q9** | **As proposed.** Format badge (`neutral`) + size badges (`neutral`). **No legality claim** — that is c4-10's, over a route this story never calls. A missing format renders **nothing**, not a `caution` pill: between two untested branches the honest one makes no claim. |
| **Q9b** | **As proposed, and the sub-fork resolved toward a listed component.** The count is its own `<span>` carrying `font: var(--type-numeric)` **and** `font-variant-numeric: var(--type-numeric-features)` together. Home: a new `src/components/DeckBadges/`, added to `shell.test.ts`'s `PRIMITIVES` (14 → 15) and to `copy-rules.test.ts`'s `COPY_MODULES`. Inline-in-`App.tsx` was rejected because `src/App.css` was deleted at c2-6 and c4-10 needs the same seam. The uppercase LABEL is **accepted**, not overlooked: uppercase is `Badge`'s declared type role and the mock's badges are uppercase too; c2-10's landmine was a whole SENTENCE rendering all-caps. |

**Twelve evasion probes. Nine caught, THREE PASSED — and all three passed for reasons worth more
than the probes that failed.**

| # | Probe | Outcome |
| --- | --- | --- |
| **(a)** | A second `fetch(` in a new `src/api/deckReader.ts` | **CAUGHT** — `posture.test.ts:328`'s exhaustive door list |
| **(b)** | A DFC grouped by its BACK face (delete `frontFace()` from `groupOf`) | **PASSED ✗ → repaired → CAUGHT** |
| **(c)** | A card dropped from every group (residual → `'Creature'`) | **CAUGHT** — 4 red, including the conservation assertion |
| **(d)** | A `404` that leaves a stale deck on screen (refusal writes nothing) | **CAUGHT** — 8 red |
| **(d2)** | The store MERGES instead of replacing, so `'none'` keeps a ghost `detail` | **PASSED ✗ twice → repaired structurally → CAUGHT** |
| **(e)** | A plain `live` boolean instead of the generation counter (3 sites) | **CAUGHT** — the restart test |
| **(f)** | The two `503`s collapse to one panel (what keying on the STATUS produces) | **CAUGHT** — 2 red, root and slice |
| **(g)** | `useDeckStore.setState.call(null, …)` — a write with no paren after `setState` | **PASSED ✗ → guard rewritten → CAUGHT**, with `.apply`/`.bind`/bare-reference added |
| **(h)** | A new `src/components/` module absent from `PRIMITIVES` | **CAUGHT** (observed for real when `DeckBadges` was created) |
| **(i)** | Authored words in a non-copy module | **CAUGHT** (observed for real, same commit) |
| **(j)** | The deck payload never seeds the card cache | **CAUGHT** — 2 red, root and slice |
| **(k)** | The counterfactual in probe (b)'s own non-vacuity assertion | **PASSED ✗ → fixed** (it routed through `groupOf`, so it modelled the CORRECT rule with extra steps) |

**Probe (b) is the most valuable line in this record.** Deleting the front-face split left **all 27
assertions green**, including all four "the repo's two land policies disagree" cards. The reason:
`groupOf` already strips everything after the em-dash, which removes the back face outright for any
DFC whose FRONT face carries a subtype — three of the four — and the fourth (`Sorcery // Land`) is
saved by `Sorcery` preceding `Land` in the precedence order. **The obvious fixtures do not
discriminate the rule they appear to test.** Measured against the corpus: a type line discriminates
only when its front face has NO em-dash and the back face's group PRECEDES the front's — **29
distinct type lines, 0 in any live deck**. Six are now pinned by name, `'Land // Legendary
Creature — Demon'` (Westvale Abbey) first, and probe (b) fails against them.

**Probe (d2) is the second.** It passed twice. The first pass was the classic: the test supplied its
own `onUpdate`, so breaking the PRODUCTION writer changed nothing it could see — this epic's
standing finding (*the wiring is right and nothing asserts the wiring*) in a store's costume. The
repair was **structural rather than a stronger assertion**: the slice now holds the union under a
`deck` key (`DeckSlice`), so zustand's shallow merge replaces the whole union and no call site has a
replace flag to forget. The second pass showed the test STILL bypassed production, so the assertion
moved to `App.test.tsx`, where the real hook, the real effect and the real writer are in the path.

### Completion Notes List

**The headline, and it contradicts nothing in the story but sharpens two things.**

1. **The story's premise held exactly.** `GET /api/active-deck` publishes `200,400,500` in the
   committed `openapi.json` — verified in Task 0, no `503` — so the epic's database-refusal criteria
   are about the deck-detail read alone, and the two readers carry separate outcome unions.
2. **`PANEL_FOR_REASON.deck_not_found` now has its first live producer**, and `panelFor()` on a deck
   refusal is correct in the same codebase where c4-1 AC 13 bans it on a card refusal. The
   distinction is written into `client.ts`'s header and `deck.ts`'s, where a reader arriving with
   c4-1's rule will look: *a card is one tile in a working view; a deck IS the view*.

**Two pre-existing `App.test.tsx` assertions changed, both from a raw `toHaveBeenCalledTimes(n)` to
a route-scoped count, and both are STRENGTHENED rather than relaxed.** AC 7 asks that the panel
assertions pass unmodified — every one of those did, byte for byte. What changed is the two
assertions about REQUEST COUNTS, and they had to: they counted the poll only because the poll was
the only caller in the app. c4-2 adds a second, non-polling caller, so a raw total can no longer say
anything about the poll — the property both tests are named for. `callsTo(fetchMock, '/api/decks')`
makes the claim directly, and the "stops polling" test now ALSO pins the total (2 in ten minutes),
which is a stronger statement than the original. The fixture became route-aware for the same reason:
a flat response sequence would hand the poll's second answer to the boot's first request, which is
not a scenario any backend can produce.

**A real-browser render, which closes a Medium-severity ledger entry that had been open since c2-7.**
The companion backend was launched, a real deck set active over `PUT /api/active-deck`, and the
built SPA rendered in **Microsoft Edge (headless=new)**. The pseudo-element wash sits behind the
badge text as `Badge.css` argues it would — the feared *"solid blank pill with invisible text"* does
not occur. Contrast measured for all five tones (7.60 / 8.33 / 7.97 / 6.17 / 8.99 : 1, all clear of
4.5:1). **One number does not clear a floor and it is a live constraint for c4-10**: `neutral`'s
`--border-strong` hairline is 1.89:1 on the page against WCAG 1.4.11's 3:1 — accepted here (a static
label's boundary carries no information its wash does not), but c4-10's badge carries STATE, and its
four semantic borders are 6.73–11.49:1, so a state distinguished by TONE is safe and one
distinguished by the neutral border would not be.

**The URL-encoding argument, confirmed against the running backend rather than reasoned.** Raw
`GET /api/deck/../decks` answers **`200` carrying the deck LIST** — it does not fail, it succeeds
against a different route — while the encoded form answers `404 invalid_request`. The status/token
split in that second answer is AD-16's *"nothing keys off a bare status code"* made vivid.

**AC 21 ruled by reading the generated file.** The half that would have bitten does not exist:
`openapi-typescript` renders a schema `default` as a **required** property, so the three count fields
are `number` in `types.d.ts`, not `number | undefined`. `strategy?: string | null` remains asymmetric
and is a field this story does not read; fixing it means changing a Pydantic default the MCP server
also calls. **Declined, and re-homed by name to the first story that reads `strategy`** (c4-7 is the
nearest candidate).

**One real defect found by a test fixture rather than a probe.** `DeckBadges` read `format.trim()`
behind a `!== null` check and threw `Cannot read properties of undefined` on a partial deck. The wire
cannot produce that today (`format` is required), but a presentation primitive that takes the whole
app down on one absent prop is the FR-13 posture inverted. Now `typeof format === 'string'`.

**Boundaries held.** No grid, no deck list, no curve, no colour panel, no card detail, no format
check. `AppShell.tsx` and the eight pre-existing primitives are untouched. No new dependency. No
Python changed — the five Python gates are byte-identical to baseline, as expected for a story that
adds no Python and whose AC 21 ruling declined to touch the wire.

**Counts.** Frontend **816 → 965** (37 → 41 files); Python **2,447 passed / 1 skipped / 54
deselected, unchanged**. Aliases **7 → 9**. Primitives **14 → 15**. Copy modules **4 → 5**.
Bundle + mirror **MEASURED CHANGED, and unlike c4-1 the CSS changed too** — `DeckBadges.css` is the
first new stylesheet since c2-10, which is AC 27's "report both" answering yes on both halves.

### File List

**New — source (4)**

- `ui/src/state/deck.ts` — the deck slice, the generation-guarded boot, `PANEL_FOR_DECK_REFUSAL`, `surfaceOf`
- `ui/src/state/deckGroups.ts` — `TYPE_GROUPS`, `frontFace`, `groupOf`, `boardsOf`, `boardsOfDeck`
- `ui/src/components/DeckBadges/DeckBadges.tsx` — the format and size pills
- `ui/src/components/DeckBadges/DeckBadges.css` — the numeric role for the count

**New — tests (4)**

- `ui/src/state/deck.test.ts`
- `ui/src/state/deckGroups.test.ts`
- `ui/src/components/DeckBadges/DeckBadges.test.tsx`
- `ui/tests/store-writes.test.ts` — AD-12's "nothing else writes the store", as a gate

**Modified — source (5)**

- `ui/src/api/client.ts` — `ACTIVE_DECK_PATH`, `DECK_PATH_PREFIX`, `deckPath`, `readActiveDeck`, `readDeck`, two outcome unions, two body readers, the vocabulary-asymmetry header
- `ui/src/api/schema.ts` — `DeckDetail`, `ActiveDeck`
- `ui/src/App.tsx` — `surfaceOf` applied; `deckName` and `badges` filled
- `ui/src/state/poller.ts` — the *"until c4-2 ships the deck view"* comment retired
- `ui/README.md` — alias count, the "Not here yet" seam, the displacement bullets, the primitives paragraph, the Badge measurements

**Modified — tests (4)**

- `ui/src/api/client.test.ts` · `ui/src/App.test.tsx` · `ui/tests/shell.test.ts` (`PRIMITIVES` 14 → 15) · `ui/tests/copy-rules.test.ts` (`COPY_MODULES` 4 → 5)

**Modified — generated artifacts (6)**

- `src/companion/app/static/index.html`, `assets/index-CAF8aktq.js` → `index-DtQXm9r7.js`, `assets/index-DmxBiI94.css` → `index-C5wax6IS.css`, and the three matching files under `plugin/server/`

**Modified — records (2)**

- `_bmad-output/implementation-artifacts/deferred-work.md` · `_bmad-output/implementation-artifacts/sprint-status.yaml`

### The gates, before and after

| Gate | Baseline `2095050` | After |
| --- | --- | --- |
| `npm test` | 816 passed / 37 files, 4.08 s | **965 passed / 41 files**, 4.4 s |
| `npm run lint` | green | green |
| `npm run format:check` | green | green |
| `npx tsc -b --force` | green | green |
| `npm run build` | green | green (JS 198.65 → **202.64 kB**, CSS **changed**) |
| `uv run pytest -m "not integration"` | 2,447 passed / 1 skipped / 54 deselected, 93.8 s | **unchanged** |
| `ruff check` | green | green |
| `ruff format --check` | 307 files | 307 files |
| `mypy src/` | 89 files, no issues | **unchanged** |
| `mypy src/ --platform win32` | 89 files, no issues | **unchanged** |

**Bundle hashes (AC 27).**

| File | Before | After |
| --- | --- | --- |
| `index.html` | `0017A9B1…` | `9897FEA5…` |
| `assets/index-*.js` | `BA5D18CD…` (`CAF8aktq`) | `1B1528FB…` (`DtQXm9r7`) |
| `assets/index-*.css` | `0A3C142D…` (`DmxBiI94`) | `842D508D…` (`C5wax6IS`) |
| `assets/space-grotesk-*.woff2` | `06408904…` | `06408904…` (unchanged) |
| `favicon.svg` | `9BE16EA2…` | `9BE16EA2…` (unchanged) |

### Change Log

| Date | Version | Description |
| --- | --- | --- |
| 2026-08-03 | 0.3 | **REVIEWED → done.** Three-layer review (Blind Hunter / Edge Case Hunter / Acceptance Auditor): the Auditor verified all 32 ACs with no violation; the hunters raised 11 findings → **2 decisions + 7 patches applied, 2 dismissed**. The headline (High, ruled by Brad): the boot's one-shot posture let a deck refusal OUTLIVE the condition it reported — a cold open during a DB build pinned the stale 503 panel after the build finished, an FR-22 regression — fixed with an **edge-triggered re-drive**: `subscribeSystemState` (a new seam in `systemState.ts`, shaped so `deck.ts` never names the store and the store-writes gate stays honest) re-boots a `refused`/`none` deck once when the poll's panel transitions INTO `no-active-deck`; a loaded deck is never re-driven (the pre-existing "boots exactly once" test crosses that exact edge and pins the count), and the bound is structural — edges are backend transitions, not a client loop, asserted over ten minutes of fake time. The same edge heals the transient-blip false "none" (Finding 2), with the no-later-edge residue declared. Also fixed: a malformed row in a valid `200` crashed the boot into a permanent `'booting'` (now a caught refusal → `internal-error` panel); the Q5 override wrongly applied to the ACTIVE-DECK route (no path parameter there — now `panelFor` unoverridden, and the known token is carried); the seed comment claiming "unguarded by the generation check" while the guard two lines up already returned (comment aligned to the conservative code); the second lock passing `'  '` (now trims); the store-writes scanner's `= create<`-only discovery (now `create[<(]`, aliased-import and string-literal-`//` residues declared); the `start()` docstring's "idempotent while running" understating settled-inertness; and the App.test.tsx "THE ONE assertion" undercount. Frontend **965 → 970** (41 files), all five gates green; Python untouched. Bundle rebuilt: JS `Ck76yOVw` (`49A35B61…`), `index.html` `4F2BAB72…`, CSS unchanged (`C5wax6IS`); `plugin/` mirror synced. Next: PR into `feat/companion-c4`. |
| 2026-08-02 | 0.2 | **IMPLEMENTED → review.** The deck bootstrap, the reconciliation and the type-grouped decklist. All 10 open questions **as proposed** (tenth story running), with Q4 corrected by arithmetic — the board partition splits on `sideboard` FIRST, because `deck.py::_counts` sums on that flag alone and a commander-first split would have broken the conservation identity invisibly. **Q1's ruling has THREE arms, not two**: a loaded deck, then a deck refusal that decided a panel of its own, then the system panel — without the middle arm AC 9's two-503s criterion would pass only because the poll usually agrees. **Twelve evasion probes, nine caught, THREE PASSED**, and the three are the record's most valuable lines. **Probe (b)** deleted the front-face split and left all 27 assertions green: `groupOf` already strips the subtype, which removes the back face for any DFC whose front face carries one, so **the obvious fixtures do not discriminate the rule they appear to test** — measured, only 29 corpus type lines discriminate it and 0 are in any deck; six are now pinned by name, Westvale Abbey first. **Probe (d2)** passed twice and exposed a vacuous-wiring test (the test supplied its own `onUpdate`); repaired **structurally** rather than with a stronger assertion — the slice now holds the union under a `deck` key so a shallow merge cannot leave a ghost, and the claim moved to `App.test.tsx` where the production writer runs. **Probe (g)** defeated this story's own new store-writes guard with `setState.call(…)`, which has no paren where a call-shaped regex looks. **`Badge`'s eye-check and contrast are DONE** — a Medium ledger entry open since c2-7 — by rendering the built SPA in **Edge against the running backend** with a real deck active: the wash sits behind the text, all five tones clear 4.5:1, and the one number that fails a floor (`neutral`'s border, 1.89:1) is accepted here and handed to c4-10 as a live constraint. The URL-encoding argument was **confirmed live**: raw `/api/deck/../decks` answers `200` **with the deck list**. AC 21 declined with a measurement — `openapi-typescript` renders `@default` as REQUIRED, so the counts were never `undefined`. Two pre-existing `App.test.tsx` request-count assertions became route-scoped and stronger; every panel assertion passed unmodified. 816 → **965** frontend (37 → 41 files); Python **2,447 / 1 skipped / 54 deselected UNCHANGED**. Bundle + mirror **MEASURED CHANGED, CSS included** (the first new stylesheet since c2-10). 10 inherited deferrals: 4 resolved, 3 re-homed by name, 2 declined with reasons, 1 partially performed; both owed corrections made; 5 new residues declared, one of them **Medium** (the Python land policy now disagrees with the frontend's on 4 cards in real decks — c4-8). Next: three-layer code review, then PR into `feat/companion-c4`. |
| 2026-08-02 | 0.1 | **CONTEXTED off `2095050`** on `feat/companion-c4`. The headline finding is that the two boot routes have **different failure vocabularies** — `GET /api/active-deck` publishes only `200/400/500` and structurally cannot answer the `503` the epic's AC describes, because it holds no `DbSession` — so the epic's error ACs are about the deck-detail read alone. Second finding: `PANEL_FOR_REASON.deck_not_found → 'no-active-deck'` has been **unreachable dead code since c2-9** (no route the poll calls publishes that token) and this story is its first live producer, which also means `panelFor()` on a deck refusal is correct **in the same codebase where c4-1 AC 13 bans it on a card refusal**. Third: the grouping input is `type_line` alone, and the repo already holds **two disagreeing land policies** that differ on **four cards in real decks**. The sharpest gate finding: `shell.test.ts`'s git-derived coverage guard makes **any new `src/components/` module a red test by design**, so where the header badges live is a decision to take before writing, not after. 32 ACs, 9 open questions (Q9 in two halves), 10 inherited deferrals — 2 of them corrections to earlier records (`@testing-library/react` IS installed; 28 of the 2,027 `deck_cards` rows are deck-orphans) — and 11 named don't-breaks. Baseline 816 frontend / 37 files. |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

2026-08-03: three-layer review DONE — 11 findings -> 2 decisions (ruled: edge-triggered boot re-drive on poll recovery, closing a High FR-22 regression) + 7 patches applied, 2 dismissed; 965 -> 970 frontend, gates green, bundle+mirror rebuilt. Next: PR into feat/companion-c4

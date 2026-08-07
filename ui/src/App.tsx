import { useEffect } from 'react'

import { AnalysisRow } from './components/AnalysisRow/AnalysisRow'
import { AppShell } from './components/AppShell/AppShell'
import { DeckBadges } from './components/DeckBadges/DeckBadges'
import { Footer } from './components/Footer/Footer'
import { StatePanel } from './components/StatePanel/StatePanel'
import { CardDetail } from './containers/CardDetail/CardDetail'
import { CardGrid } from './containers/CardGrid/CardGrid'
import { ColourDistribution } from './containers/ColourDistribution/ColourDistribution'
import { DeckList } from './containers/DeckList/DeckList'
import { FormatCheck } from './containers/FormatCheck/FormatCheck'
import { ManaCurve } from './containers/ManaCurve/ManaCurve'
import { SkipLink } from './containers/SkipLink/SkipLink'
import { hydrateDeckCards } from './state/cards'
import { surfaceOf, useDeckState } from './state/deck'
import { deckIsEmpty } from './state/deckGroups'
import { clearFormatCheck, loadFormatCheck } from './state/formatCheck'
import { useSystemState } from './state/systemState'

/**
 * The application root.
 *
 * It composes the shell, the card grid, one state panel, the header badges and the attribution,
 * and nothing else. Every other region the shell holds open — the two analysis panels, the card
 * detail, the deck list, the format check, the agent-view nav and the agent view itself —
 * arrives as a prop from a later story, so this file's job is to stay as close to one line as it
 * honestly can.
 *
 * c4-1 owns the card cache and the in-flight deduping that will feed those props, extending the
 * store and the fetch layer **c3-9** opened; until then the shell renders its own placeholders,
 * each naming the story that replaces it.
 *
 * ================= THE LEFT COLUMN IS NOW WIRE-DRIVEN (c3-9, FR-22) ====================
 *
 * `useSystemState` polls `GET /api/decks` and reports which system panel is true right now. The
 * panel is chosen from the response's `reason` TOKEN through `states.ts`'s `PANEL_FOR_REASON` —
 * never from a bare status code, which is AD-16's rule and the reason two different `503`s put
 * two different panels on the glass. Nothing here decides anything: this file renders whichever
 * panel the boundary picked, and the deck names that one of them carries.
 *
 * WHY THE TERNARY, RATHER THAN `state={panel}`: `StatePanelProps` is a DISCRIMINATED UNION, and
 * only the `no-active-deck` arm accepts `decks` — `EXPERIENCE.md` attaches a deck list to that
 * row and to no other. Spreading one `decks` prop across every state would compile only if that
 * constraint were removed. The two branches are the constraint being honoured, not a special
 * case: it is exactly one `<StatePanel>` on screen either way.
 *
 * THE DISPLACEMENT c2-9 ACCEPTED IS UNCHANGED, AND STILL NOT PAPERED OVER: `AppShell`'s
 * left-column placeholder — the line naming c4-4 and c4-8 — is DISPLACED by this prop, never
 * deleted. It still fires whenever `left` is empty and `AppShell.test.tsx` still asserts it
 * against the component's own props. What c3-9 changed is only that the choice is no longer a
 * constant; **c4-2 / c4-4** replace it again with a deck when there is a deck.
 *
 * THE `decks` PROP IS NOW PASSED, and that is this story's other half. `GET /api/decks` shipped
 * in **c3-1** and nothing called it until now; an empty list is still the ordinary fresh-install
 * answer and still renders nothing extra (StatePanel AC 5). **c4-2** owns reading the deck
 * itself — this story reads the names, which is all the panel's copy promises.
 *
 * ================= AND NOW THERE IS A DECK (c4-2, FR-07, FR-05) ========================
 *
 * `useDeckState` boots once per mount: `GET /api/active-deck`, then — on a non-null id —
 * `GET /api/deck/{deck_id}`. **The precedence between a deck and a system panel is NOT decided
 * here.** `surfaceOf` is the one place it lives (c4-2 Q1), exported from `src/state/deck.ts` so
 * that c4-4's grid, c4-7's deck list and c4-12's empty state read the same answer rather than
 * each re-deriving it from `deck !== null` — which is the epic's *"the grid and the list panel
 * cannot disagree"* clause applied one level up. This file renders the answer and computes none
 * of it; `deck` below is a NARROWING of that answer, not a second rule.
 *
 * BOTH HOOKS ARE CALLED HERE BECAUSE BOTH OWNERSHIPS LIVE HERE. `useSystemState` owns the poll
 * and `useDeckState` owns the boot, and each one's docstring says `App` is its ONE consumer for
 * the same measured reason: a second mounted caller creates a second poller / a second boot and
 * silently doubles the request rate.
 *
 * ================= AND NOW THE DECK IS ON THE GLASS (c4-4, FR-19) ======================
 *
 * The `left` slot finally holds a `CardGrid`. Until this story a loaded deck displaced the system
 * panel and put nothing in its place, so the slot fell back to `AppShell`'s own placeholder —
 * *"The card-art grid lands here — c4-4 …"* — which was the honest displacement rather than a
 * regression, and what made this story's slot findable by searching for its own id. That line is
 * now displaced in turn: **the fourth application of the c2-9 ruling, and the same one.**
 * `AppShell.tsx` is NOT edited, its placeholder still fires whenever `left` is empty, and
 * `AppShell.test.tsx` still asserts it against the component's own props. What changed is only
 * which of the two the running app shows — and `App.test.tsx`'s displacement assertion changed
 * with it, which is the point of that assertion existing.
 *
 * `CardGrid` is the first component in this codebase that is NOT a presentation-only primitive.
 * It lives in `src/containers/`, the category c4-4 ruled into existence (Q1), because a tile that
 * takes `<img onLoad>` and holds a `ref` is banned outright from `src/components/` by four
 * separate guards. `ui/README.md` carries the argument; ~15 later component stories inherit it.
 *
 * Nothing about the precedence moved. `surfaceOf` still decides, this file still renders the
 * answer and computes none of it, and the grid is handed `surface.boards` — the derivation
 * `deckGroups.ts` performed once at write time *"so the grid and the list panel cannot
 * disagree"*. **c4-7**'s deck list reads the same value, including the sideboard this grid
 * deliberately does not draw.
 *
 * ================= AND NOW THE DECK RESPONDS (c4-5, FR-17) =============================
 *
 * The `right` slot holds the card detail panel — the fifth application of the c2-9 displacement
 * ruling, unchanged: `AppShell.tsx` is NOT edited, its placeholder (*"Card detail — c4-5 — the
 * deck list — c4-7 — and the format check — c4-10 — stack here"*) still fires whenever `right`
 * is empty, and `AppShell.test.tsx` still asserts it against the component's own props. What
 * changed is which of the two the running app shows — and only for a deck.
 *
 * ================= WHAT THE RIGHT COLUMN DOES BEHIND A STATE PANEL (c4-5 Q14) ==========
 *
 * **This is a ruling, and it closes a gap in the UX contract rather than one in this story.**
 * `validation-report-2026-07-25.md:78` records it as **L8** — *"Right-column panel visibility is
 * specified for cold-open-no-deck but not for the database-not-initialized or disconnected
 * states, which also put a State panel in the left column"* — and `:146` records the lows as
 * unactioned. The two halves of the contract genuinely disagree: `EXPERIENCE.md:112` says *"Right
 * column panels hidden"* for the one case it covers, while UX-DR30 says *"the right column, nav
 * and footer remain functional around it"*.
 *
 * `surfaceOf` returns `{ kind: 'panel' }` for all six state keys, so this file is where the
 * contradiction becomes code. **Ruled: the detail panel renders only for `kind === 'deck'`.**
 * The reason is not symmetry, it is that UX-DR20's *"never empty while a deck is loaded"* has
 * nothing to be true of otherwise — a persistent card panel with no deck behind it would either
 * be an empty box or would keep showing a card from a deck that is no longer on the glass. The
 * one case the contract DOES specify is honoured exactly, the other five are made to match it,
 * and UX-DR30 stays satisfied because the column is still there with the shell's own line in it.
 * **c4-7 and c4-10 inherit this rather than re-deciding it**, which is what makes it worth
 * writing here instead of in the panel.
 *
 * The `undefined` (rather than `null`) is the same spelling the header props use, and `filled()`
 * makes either safe — see the `deckName` note below.
 *
 * ================= THE `h1` STOPS SAYING WHAT THE KICKER SAYS (C3 retro F2) ============
 *
 * `deckName` is filled with the deck's own name, so the header stops rendering the product name
 * twice — recorded at the C3 retro *"so c4-2 does not treat the swap as cosmetic"*. `AppShell`
 * is NOT edited: the element, its level and its position do not move, which is the whole point
 * of it being a prop, and its `filled()` fallback still fires when there is no deck — which is
 * what keeps a fresh install from being heading-less (c2-6 Q3). `undefined` rather than `''` is
 * deliberate on both header props, though `filled()` makes either safe.
 *
 * ================= WHY THE FOOTER IS NO LONGER A PLACEHOLDER (c2-10) ====================
 *
 * The attribution is a CONDITION OF PUBLIC RELEASE (`DESIGN.md:375`, NFR-08, UX-DR32), not a
 * design choice, so unlike every other slot this one is not waiting for data — it is correct
 * from day one and stays correct forever. There is nothing a later story replaces it with.
 *
 * The same displacement c2-9 performed on the left column applies here, for the same reason and
 * with the same care: `AppShell`'s footer placeholder — the line naming c2-10 — is DISPLACED by
 * this prop, not deleted. It still fires whenever `footer` is empty, and `AppShell.test.tsx`
 * still asserts it against the component's own props. What changed is which of the two the
 * running app shows.
 *
 * ================= "EVERY SURFACE", STRUCTURALLY (Q3, Brad 2026-07-30) ==================
 *
 * The epic asks the attribution to be present on EVERY top-level surface. Today there is exactly
 * one, so an enumerated list of surfaces would be a list its author thought of — this epic's
 * standing finding, three rounds running. The rule is structural instead, and it is already true
 * by construction: **there is one `AppShell`, one `footer` slot and no router, so every surface
 * renders through this file.** `App.test.tsx` asserts the footer is in the `contentinfo`
 * landmark by role and by text, and `ui/README.md` records the rule where the next surface's
 * author will read it.
 *
 * That holds through Epic 6 without amendment: c6-5's agent view is an OVERLAY rendered inside
 * the shell (`AppShell`'s `overlay` slot), not a route that replaces it, so the footer survives
 * it by construction rather than by anyone remembering.
 */
export default function App() {
  const system = useSystemState()
  const surface = surfaceOf(useDeckState(), system)
  // The one narrowing of the one rule. Not a second precedence decision: `surfaceOf` has already
  // said which of the two is true, and this line only gives the deck arm a name so that the
  // three slots below can read its fields without repeating the discriminant check.
  const deck = surface.kind === 'deck' ? surface : null
  const detail = deck?.detail ?? null
  // THE DECK'S ID, AS A STRING, AND THAT IS THE WHOLE OF THE FORMAT CHECK'S DEPENDENCY (c4-10 Q5,
  // Q7, AC 10). `detail` is a fresh OBJECT on every boot — the poll-recovery re-drive re-writes it
  // with the same deck in it — so keying the effect below on `detail` would re-request this route
  // on a re-boot and quietly break c4-2's per-mount request count. A string identity is what makes
  // "one format-check request per deck id per mount" structurally true rather than carefully true.
  const deckId = detail?.id ?? null

  // THE EMPTY DECK, READ ONCE (c4-12, Q1, AC 1, AC 7, AC 9, AC 10, AC 12).
  //
  // A deck with zero cards on every board is a `{kind:'deck'}` surface exactly like a full one —
  // `deck.ts` settles any 200 that way and `boardsOfDeck` over `cards: []` yields three empty
  // boards — so there is NO new `Surface` arm and no third re-derivation from `deck !== null`
  // (c4-2's decide-once ruling). The predicate itself lives beside `DeckBoards` in
  // `deckGroups.ts`, which is the module that OWNS that type and produces it; see its docstring
  // for why one expression exists rather than a fifth spelling, and for the sideboard ruling it
  // inherits from `hasCards` below.
  //
  // It is read HERE, above both effects, because two consumers need it at different moments: the
  // format check's request (suppressed for an empty deck, below) and the format check's RENDER
  // (gated in the right column). Computing it twice would be the drift `deckGroups.ts` exists to
  // prevent, in the one file that already reads the derivation three ways.
  const emptyDeck = deck !== null && deckIsEmpty(deck.boards)

  // THE DECK-WIDE HYDRATION SWEEP (c4-6, Q1, AC 23), AND ITS PLACEMENT IS THE DECISION.
  //
  // c4-6's flip control must render "when its tile renders", and whether a card HAS a back face
  // lives only in the hydrated record — `CardSummary` carries neither `card_faces` nor
  // `image_uris`. So something has to hydrate the deck rather than one card at a time. The two
  // alternatives were priced and declined in that story's Q1: a derived field on `CardSummary` is
  // an MCP-visible schema change, and a control that appears only once a card happens to be
  // inspected would materialise a Tab stop mid-traverse (UX-DR40 puts it "immediately after its
  // own tile").
  //
  // ==== WHY HERE, AND NOT IN `createDeckBoot` BESIDE `seedCardSummaries` ================
  // React runs effects AFTER the DOM commit, so the sweep is off the render's critical path: the
  // grid draws from the summary tier and never waits for a card record. Called from the boot
  // instead, the same 99 reads would be issued before React had rendered a single tile.
  //
  // **AND THE STRONGER CLAIM THIS COMMENT USED TO MAKE IS FALSE — MEASURED, AND CORRECTED
  // RATHER THAN SMOOTHED OVER.** It read "by the time this line runs the browser has already
  // queued all ~99 image requests, so the sweep takes the connection pool BEHIND the pictures".
  // Measured over four cold-cache Chrome runs against the real 99-card Atraxa deck, the first
  // card-record request starts **6–10 ms BEFORE** the first image request every time
  // (108/114, 757/765, 583/593, 105/113 ms). The commit sets the `src` attributes; the browser
  // dispatches those loads asynchronously, and this effect gets there first. React's ordering
  // buys "not on the render path", not "behind the pictures".
  //
  // ==== WHAT IT COSTS, AS A NUMBER (AC 23) ==============================================
  // At most one request per DISTINCT card id, once per deck per tab: **99** for the largest of the
  // 42 real decks (40 when this was first measured at c4-6 — the count moved, the maximum did
  // not; re-keyed at c4-12 per AC 30), fewer for all the others. `hydrateCard` dedupes in flight, refuses a hydrated
  // id and never re-asks a terminal refusal, so a re-render costs nothing and the ceiling holds.
  // `App.test.tsx` pins the count for its own fixture rather than trusting this comment.
  //
  // The wall-clock price, measured the only way that means anything — the same deck, the same
  // machine, a fresh browser profile each time, with this line and without it. Time from
  // navigation to the LAST of the deck's images:
  //
  //   with the sweep    1,594 · 1,793 · 1,795 · 847 ms      (99 card reads, all settled by ~1.0 s)
  //   without it          343 ·   753 ·   538 · 352 ms      (1 card read)
  //
  // So the tail of the cold open roughly TRIPLES — about **+1.2 s** on the largest real deck —
  // while first paint is untouched (32–128 ms either way, because the grid never waits for this).
  // That is the price of AC 1 being true at all: `CardSummary` carries neither `card_faces` nor
  // `image_uris`, so without these reads no tile can know it has a back face and no flip control
  // exists. It is a COLD-OPEN cost, once per deck per tab, and it is stated here rather than
  // discovered later.
  //
  // `detail` is the dependency because it is the DECK's identity as far as this file is
  // concerned: `deck.ts` writes it once per boot, so it changes exactly when the deck does. This
  // reads the payload's own `cards` array verbatim — not `boards` — so it is not a second
  // flattening of the derivation `deckGroups.ts` owns (AD-12), and it therefore also covers the
  // sideboard rows c4-7 will draw.
  //
  // ==== ⚠️ THIS EFFECT IS DECLARED FIRST, AND THAT IS LOAD-BEARING (c4-12, Q10, AC 20) ==
  // React runs effects in DECLARATION ORDER, so the 99 reads below are issued BEFORE the format
  // check declared under them. The transport is HTTP/1.1 (`server.py` — uvicorn's default h11, no
  // h2) and Chrome caps 6 connections per origin, so that ordering decides where the format
  // check's single request sits in the queue. **Measured over CDP against the committed SPA and
  // the running backend, Chrome 151, 2026-08-07, on the real 99-card Atraxa deck:**
  //
  //   as shipped (this first)     format-check request at queue position 106–107; full layout
  //                               311 / 363 / 428 ms (min/median/max, n=5, fresh profile)
  //   the two blocks SWAPPED      queue position 7; full layout 120 / 185 / 520 ms (n=5)
  //
  // So the order is worth roughly **180 ms of the six-surface layout time** and it is nobody's
  // accident: this comment and the one below now each name the other's queue position, because
  // before this story neither mentioned the other at all and the next reader would have reordered
  // them without knowing what moved.
  //
  // **NOT SWAPPED, and that is the ruling rather than an oversight.** The budget is NFR-05's
  // 1 second and the shipped order meets it with ≥572 ms of headroom in every one of the 13
  // recorded runs across all three arms (n=5 fresh profile, n=5 warm HTTP cache, n=3 cold image
  // cache; worst full layout 428 ms), so the swap is an unrequested behaviour change to the cold-open
  // path — measured, recorded, and left for whoever owns the improvement. It also is not free:
  // the swapped arm's spread was WIDER (120–520 ms against 311–428 ms), because moving the format
  // check ahead of the sweep moves it ahead of the images too.
  useEffect(() => {
    if (detail === null) return
    hydrateDeckCards(detail.cards.map((row) => row.card_id))
  }, [detail])

  // THE FORMAT CHECK'S ONE READ (c4-10, Q5, Q6, Q7, AC 9–12).
  //
  // ==== WHY IT IS DRIVEN FROM HERE AND NOT FROM THE PANEL ==============================
  // A container MAY NOT reach the network (`shell.test.ts:2071-2086` refuses `fetch`, `zustand`
  // and `.setState` in every container module) and `App.tsx` may not either
  // (`posture.test.ts:344-357` asserts this file does not match the network family). `client.ts`
  // is the one door, so `src/state/formatCheck.ts` owns the request and this line owns the
  // DECISION to make it — the same split `hydrateDeckCards` above already uses, one story later.
  // This file calls a state action and imports no client.
  //
  // ==== WHY NOT INSIDE `createDeckBoot`, WHICH IS THE OBVIOUS PLACE ====================
  // It would make a panel's data a FIRST-PAINT dependency of the whole deck view, and it would
  // put a network outcome inside the value whose reference identity IS the deck's identity —
  // `deckMemory.ts` and `CardDetail`'s effect both read `boards` that way, so a report landing
  // would read as a deck replacement and release the user's pin. The measured cost is worth
  // stating for the same reason: this is a SECOND `get_deck_with_cards` on the backend, not a
  // second validation — 5.2 ms median, 33.8 ms worst, measured over the then-40 real decks
  // in-process (42 at c4-12's re-key, AC 30; two more decks move neither number's order).
  //
  // ==== AND WHY IT CLEARS ==============================================================
  // Without the `null` arm a report would outlive its deck: a deck deleted between two polls
  // leaves the surface a state panel while the right column's third box still asserts a legality
  // verdict about a deck that is no longer on the glass. `clearFormatCheck` also bumps the
  // slice's generation, so a read in flight when the deck goes away writes nothing.
  //
  // ONE REQUEST PER DECK ID PER MOUNT, and no refetch (Q7): `deck_changed` is **c7-3's**, and
  // half-building a refetch here would be a second coalescing rule to reconcile with that one.
  //
  // THE CLEANUP IS THE TEARDOWN HALF OF THE CITED PRECEDENT (c4-10 review): `createDeckBoot`
  // pairs `start()` with `stop()` on cleanup, and this effect's first draft omitted its half —
  // so an in-flight read survived unmount and wrote to the store, and a StrictMode dev remount
  // fired a second WIRE request (the generation counter makes the second write harmless, not the
  // request). `clearFormatCheck` bumps the generation, which abandons the in-flight read; on a
  // deps change it runs before the next load, which re-drives from `'idle'` exactly as a deck
  // switch already did through the loading write.
  //
  // ==== AND WHY AN EMPTY DECK DOES NOT ASK AT ALL (c4-12, Q4, AC 10) ===================
  // The request is suppressed rather than made-and-ignored, and the reason is not thrift. The
  // precedent is already asserted one story back — `App.test.tsx` pins "no format-check request
  // behind a state panel" — and this is the same rule for the same reason: a panel that cannot
  // be seen must not be a round trip on the one path NFR-05 measures.
  //
  // What the answer WOULD have been is worth writing down, because it is the honest argument for
  // hiding the panel and neither artefact makes it. Run against the real validator (measured
  // 2026-08-07, `format_check` over a zero-card deck, `standard` and `brawl` identical): SIX rows,
  // nothing raised, nothing 404'd — one true `size` violation ("Mainboard has 0 cards; the
  // minimum is 60") and **four vacuous greens**: *"Every card is legal in standard"*, *"No card
  // exceeds the copy limit"*, *"No card is banned in standard"*, *"Sideboard has 0 cards"*. Three
  // of those are confident assertions ABOUT ZERO CARDS — technically true, rhetorically false —
  // and `routes/decks.py` names the failure mode in its own comment. That is what the panel would
  // have said to someone who has not added a card yet.
  //
  // `emptyDeck` is in the deps rather than folded into `deckId`, so a deck that gains its first
  // card while the tab is open WOULD ask then — today the only shipped path that rewrites
  // `detail` mid-session is the poll-recovery re-drive (c4-2), so the edge is real only in that
  // corner until c7-3's `deck_changed` refetch lands; the dep is the forward contract, not a live
  // feature (code-review correction, 2026-08-07). It is a BOOLEAN, so the poll-recovery re-drive
  // (which rewrites `detail` with the same deck in it) still recomputes to the same value and
  // issues nothing.
  //
  // ⚠️ EVERY PATH THROUGH THIS EFFECT CLEARS, and the empty/null arm clears EAGERLY ON ENTRY
  // rather than registering a cleanup — only the load arm returns `clearFormatCheck` (an arm that
  // takes the early return has no in-flight read to abandon at unmount; what it must kill is the
  // PREVIOUS deck's report, now, before this render shows it). c4-10's review found the missing
  // cleanup half once already; an empty deck taking the early return must still CLEAR, or a
  // report from the previous deck outlives it. (First written as "the teardown arm is
  // UNCONDITIONAL" — literally false about the shape; corrected at code review 2026-08-07.)
  //
  // ==== ⚠️ THIS EFFECT IS DECLARED SECOND, BEHIND THE SWEEP (c4-12, Q10, AC 20) ========
  // The other half of the decision written above the sweep — read that comment for the numbers;
  // this one states the consequence FOR THIS PANEL, because it is the one that pays for it.
  //
  // This request costs the backend **5.0 ms** (measured in-process, of which `format_check()`
  // itself is 0.07 ms — the rest is a duplicated `get_deck_with_cards` the route's own comment
  // flags). It is nonetheless **the last of AC 15's six named surfaces to paint, by a wide
  // margin**: `FormatCheck` renders `null` until its report lands, so the panel does not exist
  // until this request is answered — and because the effect above is declared first, the request
  // is queued at position **106–107** behind the 99-card sweep and the images, through six HTTP/1.1
  // sockets. Measured 2026-08-07 in Chrome: the other five surfaces are all in the DOM at ~205 ms
  // and this one arrives at 311–428 ms. **A 5 ms read is 200 ms of the layout time.**
  //
  // Moving this block ABOVE the sweep puts it at queue position 7 and roughly halves the number.
  // It is not done here (the budget is met with headroom either way — see the sweep's comment),
  // and this note exists so that the day someone needs the 180 ms, the lever is already priced.
  //
  // ⚠️ DO NOT REORDER EITHER BLOCK WITHOUT RE-MEASURING. That is the whole reason both comments
  // now name the other's queue position.
  useEffect(() => {
    if (deckId === null || emptyDeck) {
      clearFormatCheck()
      return
    }
    void loadFormatCheck(deckId)
    return clearFormatCheck
  }, [deckId, emptyDeck])

  // THE SKIP LINK'S PRESENCE CONDITION (c4-11, AC 4, Q3), AND IT IS ONE TEST COVERING THREE CASES.
  //
  // UX-DR31 says "any surface rendering a POPULATED grid"; `EXPERIENCE.md:100` contradicts itself
  // inside a single table row — its *Use* column says "First Tab stop on every surface" while its
  // body says "Present on every surface that renders a populated grid". And an EMPTY deck (c4-12)
  // satisfies neither branch of the written rule: it renders no state panel, so the withdrawal
  // trigger is absent, and its grid is not populated, so the presence trigger is absent too.
  //
  // Ruled: present iff a deck is on the glass AND it has at least one card. That covers the state
  // panel (no deck) and c4-12's empty deck (no cards). The reason is that an empty deck has
  // NOTHING TO SKIP — zero tiles and zero rows between the link and the right column, so the link
  // would save zero Tab stops. NOT because the target would be missing: `CardDetail` renders its
  // frame (carrying `SKIP_TARGET_ID`) and the `Panel` `<h2>` unconditionally — AC 7's own
  // "the panel is always there" region test pins that — and UX-DR20's "first card of the first
  // type group" fills the panel's CONTENT, not its heading. (The first written form of this
  // comment claimed the target would not exist; corrected at code review 2026-08-07.)
  //
  // Read off `surface` and `boards`, NOT re-derived: `deck.ts:388-390` warns by name that
  // `surfaceOf` exists so its consumers "read the same answer rather than each re-deriving it from
  // `deck !== null`". The card test spans EVERY board the corridor draws from — commander plus
  // mainboard (the set `CardGrid.tsx:76` spreads into tiles) AND the sideboard, because c4-7's
  // deck list renders a focusable row per sideboard card too (`DeckList.tsx:251-274`). A
  // sideboard-only deck has no tiles but still has a corridor of rows, and it was the code-review
  // ruling (2026-08-07, review of this story) that the link's condition is "any focusable deck
  // row exists", not "any tile exists" — the tile-only spelling withdrew the link from a state
  // neither of Q3's two documented cases covers.
  //
  // ==== THE BOARD TEST MOVED, AND THE RULING DID NOT (c4-12, Q1) =======================
  // Everything above still holds word for word; what changed is WHERE the three-board expression
  // lives. c4-12 needs the same question answered for its empty-deck line, and two spellings of
  // "does this deck have anything in it" in one file is the drift `deckGroups.ts` was written to
  // prevent. So the expression is `deckIsEmpty` beside `DeckBoards`, and this line is its exact
  // negation — a change to the sideboard clause is now structurally a change to both, instead of
  // a change to one that a reviewer has to notice was not made to the other.
  const hasCards = deck !== null && !emptyDeck

  return (
    <AppShell
      skipLink={hasCards ? <SkipLink /> : undefined}
      deckName={deck?.detail.name}
      badges={
        deck === null ? undefined : (
          <DeckBadges
            format={deck.detail.format}
            mainboardCount={deck.detail.mainboard_count}
            sideboardCount={deck.detail.sideboard_count}
          />
        )
      }
      /* THE LEFT COLUMN NOW STACKS THE GRID AND THE ANALYSIS ROW (c4-8, AC 1, AC 2, AC 3).
         A Fragment, exactly as the right column took one at c4-7, and for the same reason:
         `.app-shell-column` is already `display:flex; flex-direction:column; gap:
         var(--space-panel-gap)` (AppShell.css:151-156), so a second child stacks 24px beneath
         the grid with no shell edit. `AppShell.tsx` is NOT touched — the SEVENTH application of
         c2-9's displacement ruling, and the first on the LEFT slot since c4-4. Its placeholder
         (the line naming c4-4, c4-8 and c4-9) still fires whenever `left` is empty, which
         `AppShell.test.tsx:115` asserts against the component's own props.

         `AnalysisRow` rather than the panel directly, because `AppShell.tsx:127` assigns the
         1:1 pair to THIS story by name and c4-9 supplies the second panel: the row renders one
         child at full width today and two at exactly 1:1 the day that story lands, by adding a
         sibling inside this element and editing nothing else (Q6).

         Gated on the SAME `kind === 'deck'` test as the grid beside it, inherited from the
         c4-5 Q14 ruling rather than re-decided here (AC 3) — and note this is a DIFFERENT gate
         from the right column's: the left slot renders a `StatePanel` in the other five cases,
         not a placeholder.

         ==== THE ROW HAS ITS SECOND CHILD (c4-9, AC 1, AC 2), AND NOTHING ELSE HERE MOVED ====
         `AnalysisRow` was built at c4-8 to be right twice — one child filling the width, two at
         exactly 1:1 — so this story lands by adding a sibling and editing neither that component
         nor `AppShell.tsx`. The EIGHTH application of c2-9's displacement ruling; the shell's
         left-column placeholder (the line naming c4-4, c4-8 and c4-9) still fires whenever
         `left` is empty, which `AppShell.test.tsx:115` asserts against the component's own props.
         Document order is the contract: the curve first, the colour bar second, matching
         DESIGN.md's *"the mana-curve and color-distribution panels below it as a 1:1 pair"*.

         ==== AND THE EMPTY ROW IS NO LONGER THIS FILE'S PROBLEM (c4-9, Q10, AC 33) =========
         Each panel still owns its own emptiness — `ManaCurve` renders nothing for a zero curve,
         `ColourDistribution` nothing for a zero pip total — and this comment used to end by
         accepting the row's EMPTY div surviving in the DOM with the column gap still applied
         beneath the grid, because gating it here would need a derivation this file must not
         perform. That is CLOSED, and not here: `.analysis-row:empty { display: none }` lets the
         row answer for itself, with no total in this file, no second derivation of anything, and
         no `App.tsx` edit at all. Story 4.12 inherits it. */
      left={
        surface.kind === 'deck' ? (
          <>
            <CardGrid boards={surface.boards} />
            <AnalysisRow>
              <ManaCurve boards={surface.boards} />
              <ColourDistribution boards={surface.boards} />
            </AnalysisRow>
          </>
        ) : surface.panel === 'no-active-deck' ? (
          <StatePanel state="no-active-deck" decks={system.decks} />
        ) : (
          <StatePanel state={surface.panel} />
        )
      }
      /* THE RIGHT COLUMN NOW STACKS TWO PANELS (c4-7, AC 1, AC 2, AC 3).
         A Fragment, and nothing else is needed: `.app-shell-column` is already
         `display:flex; flex-direction:column; gap: var(--space-panel-gap)` (AppShell.css:151-156),
         so a second child stacks 24px beneath the first with no shell edit. `AppShell.tsx` is NOT
         touched — the sixth application of c2-9's displacement ruling, and its `/c4-7/`
         placeholder still fires whenever `right` is empty, which `AppShell.test.tsx:161`/`:171`
         assert against the component's own props.

         BOTH panels are gated on the SAME `kind === 'deck'` test, inherited from the c4-5 Q14
         ruling above rather than re-decided here (AC 2). The deck list is permanently present
         beside the grid — never a toggled alternate view (FR-05, UX-DR19) — so there is no
         view-mode state anywhere in this file.

         ==== AND NOW THERE ARE THREE (c4-10, AC 1, AC 2, AC 3) ============================
         The **ninth** application of c2-9's displacement ruling, and the story that finally
         displaces its OWN key from the shell's placeholder: that line named c4-5, c4-7 and
         **c4-10** in one string, so it has been off a rendered deck view since c4-5 — what
         changes here is that `c4-10` is now absent because its own panel is present. The C3
         retro's F1 count drops to one; the gate itself stays c8-5's. `AppShell.tsx` is NOT touched
         and `AppShell.test.tsx` still asserts the placeholder against the component's own props.

         ⚠️ CORRECTED AT c4-11 (Q14). This line named the remaining key as **`c4-11`, in the
         skip-link work** — and so did c4-9's record and `App.test.tsx`'s two comments. All three
         were wrong in the same direction, and the skip link renders no story key at all. The key
         that actually remains is **`c6-8`**: `AppShell.tsx:117` renders `slot(nav, 'Agent-view nav
         pills land here — c6-8.')` and this file never passes `nav`, so that string is on the
         glass on EVERY surface, including a fully loaded deck. It has been there since c2-6 and
         was missed because every F1 assertion below names a `c4-*` key and none looks for a `c6-*`
         one — a count that only ever checked the keys someone thought of. Asserted now.

         `.app-shell-column`'s existing `gap: var(--space-panel-gap)` stacks it 24px beneath the
         deck list with no shell edit, exactly as the deck list stacked beneath the detail panel.
         DOCUMENT ORDER IS THE CONTRACT — detail, list, format check — and `DESIGN.md:376` writes
         the column as *"card detail, deck list, format check, stacked"* in that order.

         `FormatCheck` takes NO PROP, and it is the only panel in the epic that does not: it
         reads its own slice and needs neither `boards` nor the deck payload. That is worth
         seeing here rather than only in its header — every sibling takes `boards`, and giving
         this one the same shape would have coupled it to a derivation it does not use.

         ==== AND THE ONE PANEL c4-12 HIDES (Q3, AC 7, AC 9) ==============================
         THIS IS THE ONLY NEW GATE THE EMPTY-DECK STORY ADDS, and the count is the finding.
         AC 7 names THREE panels to hide and TWO OF THEM ALREADY HIDE THEMSELVES: `ManaCurve`
         returns `null` on a zero curve total, `ColourDistribution` on a zero pip total, and
         `AnalysisRow.css`'s `:empty` rule then collapses the row that held them. All three
         shipped deliberately, naming this story — c4-9's is written as *"c4-12's clause
         arriving early … c4-12's author is told here that the row is already handled and only
         the panels' own conditions are theirs."* Adding a card-count gate for either would
         duplicate a working mechanism AND redden the land-only test, which pins those two
         panels absent on a deck that HAS cards.

         The format check is different, and its own header says why in advance: *"This panel's
         data is never empty: six rows, always. So there is no self-gate to lean on and story
         4.12 … is the only thing that will ever hide it."* So the gate is here, in `App.tsx`,
         and NOT in the panel — deliberately, so the panel keeps exactly ONE self-owned `null`
         arm (`state.status !== 'report'`, which means *a report has not arrived*, including a
         refusal that `deferred-work.md` records as silent by ruling) and this story's arm stays
         visibly a DIFFERENT decision made somewhere else. A reviewer can tell a hidden panel
         from a failed one because the two live in different files.

         `emptyDeck` and not `!hasCards` — for LEGIBILITY, not behaviour: inside this
         `surface.kind === 'deck'` branch `deck !== null`, so `!hasCards` reduces to `emptyDeck`
         identically, sideboard-only deck included (both spellings render the panel there — see
         `deckIsEmpty`'s docstring for that residue). The first draft of this comment claimed the
         two differ; they do not, and the record was corrected at code review 2026-08-07. The
         chosen spelling is the one that names the actual question, so a future edit to
         `hasCards`'s condition (say, a focusability clause for the skip link) cannot silently
         move this panel's gate with it. */
      right={
        surface.kind === 'deck' ? (
          <>
            <CardDetail boards={surface.boards} />
            <DeckList boards={surface.boards} />
            {emptyDeck ? null : <FormatCheck />}
          </>
        ) : undefined
      }
      footer={<Footer />}
    />
  )
}

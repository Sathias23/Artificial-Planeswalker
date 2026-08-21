/**
 * AD-12's second sentence, as a gate: **nothing but the wire may write the store** (story c4-2,
 * AC 18).
 *
 * The spine, verbatim: *"its state comes from exactly two inputs — REST responses and WebSocket
 * messages. Nothing else may write the store."* That is a rule about a whole codebase, and until
 * this story it was true by accident — there was one slice with one writer, so there was nothing
 * to get wrong. c4-2 adds a second slice whose value is a whole DECK, and a deck is exactly the
 * kind of thing a component reaches for a setter to nudge: a "refresh" button, an optimistic
 * update after a push, a URL parameter, a `localStorage` restore. Each of those would be a third
 * input, and none of them would fail any existing test.
 *
 * ================= KEYED ON THE WRITE, NOT ON A LIST OF FILES ==========================
 *
 * The property is *"`setState` is called from the slice that owns it, and nowhere else"*, so the
 * scan is for the CALL and the allowance is per store — an enumerated list of innocent files
 * would be a list its author thought of, which is this epic's standing review finding. A new
 * module that writes a store is red here by default and has to argue its way into the table
 * below, which is the direction that fails safe.
 *
 * **The pattern matches the METHOD, not a call**, and that is a measured correction rather than
 * a preference. The first version of this guard required `setState` to be followed by `(`, and
 * its own firing probe defeated it on the first run: `useDeckStore.setState.call(null, …)` is a
 * write in which `setState` is followed by a DOT. So is `.apply`, so is `.bind`, and so is
 * handing the bare method to something else. Every one of those is a write; none of them has a
 * paren in the place a call-shaped regex looks. Naming the method alone is both simpler and
 * strictly harder to evade — and reading `setState` without calling it is already the signal
 * this file exists to raise.
 *
 * ================= WHAT THIS CANNOT SEE, DECLARED =====================================
 *
 * A store handed to another module as a VALUE — `writeTo(useDeckStore)` — and written there. No
 * text pattern can follow that, and the answer is review, in the same division of labour
 * `token-usage.test.ts` and `copy-rules.test.ts` both declare for their own halves. What makes
 * the residue small is that the stores are not exported to anywhere that would want one: the
 * component tree cannot import a store at all (`posture.test.ts` bans the value import outright),
 * so the only modules that could do it are the four in `src/state/`.
 *
 * Second residue, found by review: {@link withoutComments} strips from `//` to end of line
 * without knowing about string literals, so a shipped line like
 * `const u = "a//b"; useDeckStore.setState(…)` would lose its write to the stripper and pass
 * this gate green. A regex cannot lex strings-containing-slashes out of comments reliably; the
 * answer is the same review division of labour, and the residue is declared here so the next
 * person probing this file does not re-discover it. (The stripper stays, because `setState`
 * NAMED IN PROSE is this file's own header four times over — see the silent-half table below.)
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

// git, not readdir — the authority every guard in this project uses, so an untracked module
// cannot pass vacuously and a committed one cannot escape CI.
const shippedModules = execFileSync('git', ['ls-files', 'src/*.ts', 'src/*.tsx'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)
  .filter((file) => !/\.test\.tsx?$/.test(file))

const withoutComments = (source: string) =>
  source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1')

/**
 * Each store, and the ONE module allowed to write it -> why that module is the owner.
 *
 * A store added without an entry here fails the completeness check below, so the table cannot
 * fall behind the code the way a hand-kept list of files would.
 */
const STORES: { store: string; owner: string; why: string }[] = [
  {
    store: 'useSystemStore',
    owner: 'src/state/systemState.ts',
    why: 'the poll is the only input to the system panel (story c3-9); `poller.ts` emits updates and this module applies them, which is why the poller itself holds no store import at all.',
  },
  {
    store: 'useDeckStore',
    owner: 'src/state/deck.ts',
    why: 'the two boot reads are the only inputs to the deck (story c4-2, AD-12). Epic 5 adds `deck_changed` as the second input, into this same module — whose c7-5 `refetchSettles` counter (the announce-once signal) is written by `applyRefetchSettles`, the third sibling writer beside `applyDeckState` and `applyUpdating`, incremented only against the refetch success settle.',
  },
  {
    store: 'useCardStore',
    owner: 'src/state/cards.ts',
    why: "the card cache's writes are `seedCardSummaries` and `hydrateCard`'s settle (story c4-1); a component that wrote an entry would defeat the in-flight deduping the whole slice exists for.",
  },
  {
    store: 'useInspectionStore',
    owner: 'src/state/inspection.ts',
    why: 'the FIRST slice whose input is a person rather than the wire (story c4-5, Q5). The spine sentence this file exists to enforce is narrowed IN THAT MODULE\'S HEADER to "nothing outside the store writes SERVER-DERIVED state", and the narrowing is safe for exactly the reason the bans below are keyed the way they are: the slice holds four card ids chosen by a hover, a focus or a click — no deck, no card record, no wire token, and nothing that any request could answer or any response contradict. The verbs (`setHovered`/`clearHovered`, `setFocused`/`clearFocused`, `togglePin`/`clearPin`, `clearTransientTargets`, `setDefaultTarget`, and c7-4\'s `evictDepartedPin` — the R9 membership-transition eviction, which reads the two decklists it is HANDED as arguments and holds no deck of its own) are the writers; the components that call them still touch no `setState`, which is what the scan below actually asserts.',
  },
  {
    store: 'useFaceStore',
    owner: 'src/state/faces.ts',
    why: "which FACE of a double-faced printing is showing (story c4-6, Q4, UX-DR15). The SECOND slice whose input is a person, inheriting c4-5's narrowing unchanged and needing no further one: it holds one non-negative integer per Scryfall printing uuid, chosen by a click on the flip control, and nothing about it is server-derived — no request can answer which face somebody wants to look at and no response can contradict it. `flipCard` is the one writer and `resetFaces` is its test-only twin; the control that calls them touches no `setState`. It is deliberately NOT cleared when a deck is replaced, which is the OPPOSITE of what `CardDetail`'s `deckMemory` does to the inspection slice three lines away — a pin names a place in a deck and is wrong the moment the deck changes, while a face index names a face of a CARD and stays right whether or not that card is on the glass (UX-DR15: \"a snap-back to the front face reads as a bug\"). Both rules are stated in this module's header so the next reader does not have to infer one from the other.",
  },
  {
    store: 'useFormatCheckStore',
    owner: 'src/state/formatCheck.ts',
    why: "the active deck's format check — the SIXTH slice, and the first since c4-2 whose input is the wire again (story c4-10, Q5). It is a store BESIDE the deck rather than a field on it, and the reason is the same one that made `DeckState` a union under a key: `boards`'s reference identity IS the deck's identity, read that way by `deckMemory.ts` and by `CardDetail`'s effect, so a report landing inside the `'deck'` arm would read as a deck REPLACEMENT and release the user's pin. Putting the request in `createDeckBoot` was rejected for a second reason as well — it would make one panel's data a first-paint dependency of the whole deck view, for a duplicated `get_deck_with_cards` on the backend. `loadFormatCheck` is the one writer and `clearFormatCheck` is its production twin (NOT a test hook, unlike `resetDeckState`): `App.tsx` calls it when there is no deck, which is what stops a legality verdict outliving the deck it describes. Staleness is a generation counter rather than a `live` boolean, for `createDeckBoot`'s argument verbatim — a deck switched mid-flight must not let the old deck's report land on the new deck's panel. The container that renders it calls no `setState` and reaches the network nowhere; `App.tsx` decides WHEN to read and this module is what reads.",
  },
  {
    store: 'useAgentViewStore',
    owner: 'src/state/agentView.ts',
    why:
      'whether an agent view is on the glass and what it is showing — the SEVENTH slice, ' +
      "and the first whose TWO fields sit on opposite sides of c4-5's narrowing (story " +
      'c6-5, AC 5, AC 6). The content is server-derived (an agent view exists because the ' +
      'agent pushed one, and since c6-6 the writer IS a WebSocket message, through ' +
      '`openSuggestionsPush` — the spine ' +
      "sentence's own second input, nothing narrowed); the open/closed status is a person, " +
      'because Esc, the close pill and a scrim click are three gestures and no request can ' +
      'answer whether somebody is still reading. They live in ONE slice because AC 5 is a ' +
      'statement about their relationship — *"dismissal never clears content"* (UX-DR34) — ' +
      'which split across two stores would have no address. `openAgentView` and ' +
      '`closeAgentView` are the writers and `resetAgentView` is their test-only twin, the ' +
      '`resetFaces` precedent; it is also the ONLY function that ever writes `content` back ' +
      'to `null`, which is what keeps UX-DR34 true of every production path. `content` is a ' +
      "SCALAR rather than a stack, so UX-DR38's permanently-one-level overlay is " +
      'unrepresentable-by-type rather than a rule anybody has to obey. Story 17.2 widened the ' +
      'retention BESIDE those fields rather than reshaping them: `history` holds the last 20 ' +
      "pushes overall (FR-18, newest-first by envelope `ts`), appended inside `openAgentView`'s " +
      'single existing `setState` — still one writer, and the history popover that renders it ' +
      'calls only the exported verbs (`reopenPush`). The container that ' +
      'renders it touches no `setState`, which is what the scan below actually asserts.',
  },
]

/** Whether one module's source writes the named store, by any spelling. See the header. */
const writes = (source: string, store: string): boolean =>
  new RegExp(`\\b${store}\\.setState\\b`).test(source) ||
  (/\bsetState\b/.test(source) && new RegExp(`\\b${store}\\b`).test(source))

/** Every module that writes the named store. */
const writersOf = (store: string): string[] =>
  shippedModules.filter((file) => writes(withoutComments(sourceOf(file)), store))

describe('every store has exactly one writer (AD-12, AC 18)', () => {
  it('is reading real modules, and finding the real writers in them (non-vacuity)', () => {
    expect(shippedModules.length).toBeGreaterThan(10)
    for (const { store, owner, why } of STORES) {
      expect(shippedModules, `${store}'s declared owner is not tracked`).toContain(owner)
      expect(why.length, `${store} is listed with no reason`).toBeGreaterThan(40)
      // The anchor that matters: if the scan silently stopped matching, every store would have
      // ZERO writers and the assertion below would pass while proving nothing.
      expect(writersOf(store), `nothing writes ${store} — the scan is broken`).toContain(owner)
    }
  })

  it.each(STORES)('$store is written only by $owner', ({ store, owner }) => {
    expect(writersOf(store)).toEqual([owner])
  })

  it('names every store that exists — the table cannot fall behind the code', () => {
    // `create<…>(` and `create(…)` are both zustand constructor spellings — the explicit
    // generic is this repo's convention, but a middleware-wrapped `create(devtools(…))` or
    // `create(combine(…))` carries no generic at all, and a review found the first version of
    // this scan was keyed to the one spelling in use. `[<(]` catches both, so a fourth slice
    // arrives here rather than quietly acquiring whatever writers it likes. Still invisible, and
    // declared as such: an ALIASED import (`import { create as makeStore }`) — no local text
    // pattern can follow a rename, and the module-scope import conventions this repo pins make
    // one a review-visible oddity in its own right.
    const declared = shippedModules.flatMap((file) => [
      ...withoutComments(sourceOf(file)).matchAll(/export const (\w+) = create[<(]/g),
    ])

    expect(declared.map((match) => match[1]).sort()).toEqual(STORES.map((s) => s.store).sort())
  })

  it.each([
    ['the plain call', 'useDeckStore.setState({ status: "none" })'],
    ['a destructured setter', 'const { setState } = useDeckStore; setState({ status: "none" })'],
    // THE PROBE THAT DEFEATED THE FIRST VERSION OF THIS GUARD, on its first run. A regex
    // requiring `setState` to be followed by `(` sees a DOT here and reports nothing. Kept at
    // the head of the reflection family below because it is the one that was found rather than
    // predicted.
    ['a .call() through the method', 'useDeckStore.setState.call(null, { status: "none" })'],
    ['an .apply()', 'useDeckStore.setState.apply(null, [{ status: "none" }])'],
    ['a bound setter stashed for later', 'const w = useDeckStore.setState.bind(useDeckStore)'],
    ['the bare method handed to something else', 'register(useDeckStore.setState)'],
    ['a spaced call', 'useDeckStore.setState ({ status: "none" })'],
  ])('would catch %s — the firing half', (_label, line) => {
    expect(writes(withoutComments(line), 'useDeckStore'), `nothing catches: ${line}`).toBe(true)
  })

  it.each([
    ['a hook read', 'const s = useDeckStore()'],
    ['an imperative read', 'const s = useDeckStore.getState()'],
    ['a subscription', 'useDeckStore.subscribe(listener)'],
    ['a selector', 'const n = useDeckStore((s) => s.status)'],
    // `setState` NAMED IN A COMMENT is not a write, which is what the comment stripper is for —
    // and this file's own header says the word four times.
    ['the word in prose', '// nothing here calls setState on useDeckStore'],
  ])('says nothing about %s — the silent half', (_label, line) => {
    // A guard that flagged the ordinary consumer spellings would be disabled within a story,
    // which is how a gate becomes a comment.
    expect(writes(withoutComments(line), 'useDeckStore')).toBe(false)
  })
})

describe('the deck slice has no input but the wire (AC 18)', () => {
  const deckSlice = withoutComments(sourceOf('src/state/deck.ts'))

  it.each([
    ['localStorage', /\blocalStorage\b/],
    ['sessionStorage', /\bsessionStorage\b/],
    ['the URL', /\b(location|URLSearchParams|history)\b/],
    ['a cookie', /\bdocument\.cookie\b/],
    ['a timer', /\b(setTimeout|setInterval|requestAnimationFrame)\s*\(/],
  ])('reads nothing from %s', (_label, pattern) => {
    // Each of these is a THIRD input, and each is the kind that arrives as a one-line
    // convenience: "remember the last deck across reloads" is a reasonable-sounding feature that
    // would make the store's contents unexplainable from the network alone.
    expect(deckSlice).not.toMatch(pattern)
  })

  it('holds no fetch of its own — the one door is still `src/api/client.ts`', () => {
    // `posture.test.ts` asserts this exhaustively over all of `src`; repeated here because this
    // is the module most likely to grow one, being the one that sequences two requests.
    expect(deckSlice).not.toMatch(/\bfetch\s*\(/)
    expect(deckSlice).not.toMatch(/\bnew WebSocket\s*\(/)
  })
})

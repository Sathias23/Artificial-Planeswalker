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
    why: 'the two boot reads are the only inputs to the deck (story c4-2, AD-12). Epic 5 adds `deck_changed` as the second input, into this same module.',
  },
  {
    store: 'useCardStore',
    owner: 'src/state/cards.ts',
    why: "the card cache's writes are `seedCardSummaries` and `hydrateCard`'s settle (story c4-1); a component that wrote an entry would defeat the in-flight deduping the whole slice exists for.",
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

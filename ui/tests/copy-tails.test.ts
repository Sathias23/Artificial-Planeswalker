/**
 * The half of `EXPERIENCE.md`'s copy rows that nothing gated (story c3-9, AC 15; Q6).
 *
 * ================= WHAT WAS UNGATED, AND WHY IT IS THIS STORY'S =========================
 *
 * `tests/copy.test.ts` reads the artefact itself and asserts every `Headline:` and every
 * re-joined `Body:` byte for byte. Its parser captures those two fields and **nothing else** —
 * `copy.test.ts:90-91` — so four clauses of the same table are contract that no gate can see.
 * They could be edited or deleted with every suite green while their TypeScript mirrors drifted
 * out from under them, which is the failure the verbatim gate exists to prevent, one column to
 * the right.
 *
 * **Three of the four constrain THIS story specifically**, which is why the ledger homed the item
 * here rather than on the next copy change:
 *
 *   | Clause | Its mirror in TypeScript |
 *   | --- | --- |
 *   | the no-active-deck row's deck-list clause | `DECKS_PATH` — the route the poll calls |
 *   | the stalled row's *"c3-9 owns the threshold"* | `STALLED_AFTER_MS`, and its `false` in `RETRIES_QUIETLY` |
 *   | the internal-error row's *"never retries itself"* | `RETRIES_QUIETLY['internal-error']` |
 *
 * The fourth — the disconnected row's *"Retrying-quietly note in the connection pill"* — was
 * **declined here and re-homed on c5-6 by name**, which owns its backoff and the `disconnected`
 * state (the PILL was c5-7's). There was nothing in this repository for it to be checked against:
 * a gate on it then would have asserted prose against prose. It was re-homed rather than left as a
 * fourth "candidate home" note, because that is what AC 15 asks for and what the previous three
 * drafts of this item did not do.
 *
 * **c5-6 PAID HALF OF IT AND c5-7 PAID THE REST (2026-08-08).** The last describe in this file is
 * no longer a placeholder: it reads the shipped backoff's constants out of `src/state/socket.ts`,
 * holds its two-gate threshold to `poller.ts`'s `STALLED_AFTER_MS`, and asserts that the loop reads
 * `RETRIES_QUIETLY` rather than paraphrasing it. c5-7 then shipped the pill, so the last clause —
 * the note itself — became checkable and its deliberate non-assertion was **converted into a real
 * mirror** rather than deleted: the row's promise is now held against the pill's shipped words AND
 * against the map the loop reads, so softening either end fails here.
 *
 * ================= WHY A NEW FILE RATHER THAN AN EDIT TO copy.test.ts ===================
 *
 * AC 16 predicts `copy.test.ts` passes **unchanged**, and "unchanged" is only worth saying if it
 * is literally true — a `git diff` of that file is the cheapest way to check the prediction. So
 * the extension lives here. The six existing verbatim assertions stay exactly as they are, and
 * this file re-parses the artefact for a DIFFERENT capture (the tail, not the two fields) rather
 * than reaching into the other suite's parser.
 *
 * ================= WHY THE MIRRORS ARE READ AND NOT IMPORTED ===========================
 *
 * **This is a KNOWN blind spot, not a discovery** — `ui/README.md`'s blind-spot table already
 * carries the row (*"A cross-project import breaking `tsc` while `npm test` stays green"*), and
 * the first draft of this file walked into it anyway, which is the entry earning its place. What
 * c3-9 adds is the measurement the row does not have.
 *
 * `tests/` belongs to `tsconfig.node.json` — `moduleResolution: nodenext`, `lib: ES2023`,
 * `types: ["node"]` — and importing an app module drags that module's WHOLE import graph into
 * that project. The first draft imported `DECKS_PATH`, `RETRIES_QUIETLY` and `STALLED_AFTER_MS`
 * directly; `npx tsc -b --force` then reported **twelve** errors in files this story mostly does
 * not even touch: `TS2835` (nodenext wants explicit `.js`/`.ts` extensions) on every relative
 * import inside `states.ts`, `poller.ts` and `decks.ts`, `TS2353` because `RequestInit.cache` is
 * a DOM type the node project has no lib for, and three cascading `TS2344`s from `states.ts`'
 * type-level asserts once its own import had failed — the row's *"cascading into errors that name
 * the importee's type asserts, not the import"*, confirmed. `npm test` was green throughout.
 *
 * `tests/copy.test.ts` gets away with importing `copy.ts` because that module has no relative
 * imports at all. That is a property of one file, not a rule, and reading it as a rule is what
 * produced the twelve errors.
 *
 * So the mirrors are read out of the SOURCE, which is what every other suite in this directory
 * does (`shell.test.ts`, `token-usage.test.ts`, `tokens.test.ts`). It costs nothing in strength
 * for the claims being made: flipping `RETRIES_QUIETLY['internal-error']` to `true` fails the
 * read exactly as it would fail an import, and re-pointing the poll fails the endpoint check
 * exactly as it would. What it does cost is a value the reader could compute with, which none of
 * these assertions needs.
 */

import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceOf = (file: string): string => readFileSync(path.join(uiRoot, file), 'utf8')

/** `export const DECKS_PATH = '/api/decks'` — the route the poll actually calls. */
const DECKS_PATH = /export const DECKS_PATH = '([^']+)'/.exec(sourceOf('src/api/client.ts'))?.[1]

/** `export const STALLED_AFTER_MS = 60_000` — the threshold `EXPERIENCE.md` held open for c3-9. */
const STALLED_AFTER_MS = Number(
  /export const STALLED_AFTER_MS = ([\d_]+)/
    .exec(sourceOf('src/state/poller.ts'))?.[1]
    ?.replaceAll('_', '') ?? NaN,
)

/**
 * Comments dropped before the entry regex ever runs: `RETRIES_QUIETLY`'s body carries a
 * docstring per entry, and a reader that sees comments as code would be satisfied by a
 * commented-out `// 'internal-error': false,` while the runtime map had lost the key — prose
 * asserted against prose, the exact failure this file's header argues against. (`tsc`'s
 * `satisfies` clause would catch the deletion independently; this keeps the GATE honest too.)
 */
const stripComments = (source: string): string =>
  source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '')

/**
 * The body of `RETRIES_QUIETLY`, and only that.
 *
 * Scoped to the one declaration rather than searched over the whole file, because `states.ts`
 * spells several of these keys in `PANEL_FOR_REASON` too — a whole-file search would read the
 * wrong map and keep reading it after somebody edited the right one.
 */
const RETRIES_QUIETLY_SOURCE = stripComments(
  /export const RETRIES_QUIETLY = \{([\s\S]*?)\n\} satisfies/.exec(
    sourceOf('src/components/StatePanel/states.ts'),
  )?.[1] ?? '',
)

/** One entry of `RETRIES_QUIETLY`, read from the map the poller consults at runtime. */
const retriesQuietly = (state: string): string | undefined =>
  new RegExp(`['"]?${state}['"]?:\\s*(true|false)`).exec(RETRIES_QUIETLY_SOURCE)?.[1]

const EXPERIENCE_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md',
    import.meta.url,
  ),
)

/**
 * Every copy row's label mapped to what is LEFT of its cell once the two gated fields are cut
 * out — the tail, which is the thing this file exists to hold.
 *
 * Same row detection as the verbatim gate (a two-cell table line carrying both `Headline:` and
 * `Body:`), deliberately: a row this parser saw and that one did not, or the reverse, would mean
 * the two gates disagree about what a copy row IS.
 */
const readTails = (raw: string = readFileSync(EXPERIENCE_MD, 'utf8')): Map<string, string> => {
  const tails = new Map<string, string>()

  for (const line of raw.split(/\r?\n/)) {
    const cells = /^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$/.exec(line)
    if (!cells) continue
    if (!/Headline:\s*"[^"]*"/.test(cells[2]) || !/Body:\s*"[^"]*"/.test(cells[2])) continue
    tails.set(
      cells[1],
      cells[2]
        .replace(/Headline:\s*"[^"]*"/, '')
        .replace(/Body:\s*"[^"]*"/, '')
        .trim(),
    )
  }

  return tails
}

const tails = readTails()

describe('the parser found the same rows the verbatim gate finds (non-vacuity)', () => {
  it('reads six rows out of the artefact', () => {
    // The same six `copy.test.ts` asserts. A drift here means one of the two parsers changed its
    // mind about what a copy row is, which is worth failing on before either gate is trusted.
    expect(tails.size).toBe(6)
  })

  it('found all three source mirrors, so no assertion below is reading a miss', () => {
    // A regex over source that stops matching returns `undefined`, and `undefined` is what a
    // deleted constant and a renamed one both look like. Anchoring the reads here is what makes
    // every `toBe('false')` below a comparison rather than a coincidence.
    expect(DECKS_PATH).toBeTypeOf('string')
    expect(STALLED_AFTER_MS).toBeGreaterThan(0)
    expect(RETRIES_QUIETLY_SOURCE).toMatch(/no-active-deck/)
    expect(retriesQuietly('no-active-deck')).toBe('false')
  })

  it('separates the tail from the gated fields — it is neither empty nor the whole cell', () => {
    const internalError = tails.get('Internal error')
    expect(internalError).toBeDefined()
    // The firing half: the tail exists…
    expect(internalError).not.toBe('')
    // …and the cutting worked, so this is a tail and not a second copy of the body.
    expect(internalError).not.toMatch(/Headline:|Body:/)
    expect(internalError).not.toContain('Restart the companion in your terminal')
  })

  it('reads no tail at all for the two rows that have none', () => {
    // `Database not initialized` and `Database updating` are Headline+Body and nothing else, so
    // an empty tail is the correct answer for them — and asserting it is what stops a future
    // "every row has a tail" rule from being written against an artefact that disagrees.
    expect(tails.get('Database not initialized')).toBe('')
    expect(tails.get('Database updating')).toBe('')
  })
})

describe('the three tails that constrain this story are gated (AC 15)', () => {
  it('the no-active-deck row still names the endpoint the poll actually calls', () => {
    const tail = tails.get('No-active-deck')

    // Both directions in one assertion pair. Delete the clause from the artefact and the first
    // fails; point the poll at a different route and the second does. Neither can move alone.
    expect(tail).toMatch(/available-deck list from/)
    expect(tail).toContain(`GET ${DECKS_PATH}`)
  })

  it('the no-active-deck row still says the list is names only and non-clickable', () => {
    // The other half of that clause, and the one `StatePanel.test.tsx` already mirrors by
    // asserting the ABSENCE of `link` and `button` roles in the panel's subtree. Gated here so
    // that deleting the sentence does not quietly delete the requirement.
    expect(tails.get('No-active-deck')).toMatch(/names only, non-clickable/)
  })

  it('the stalled row still homes the threshold on this story, and the story still has one', () => {
    const tail = tails.get('Database updating, stalled')

    expect(tail).toMatch(/the client decides when "a while" has passed/)
    expect(tail).toContain('c3-9 owns the threshold')
    // …and c3-9 does own one. The clause has been an IOU since c2-9; this is the assertion that
    // says it was paid rather than merely re-promised.
    expect(STALLED_AFTER_MS).toBeGreaterThan(0)
    // "The escalation from the row above" — an escalation that kept retrying quietly would be
    // the row above, not an escalation of it.
    expect(tail).toMatch(/escalation from the row above/)
    expect(retriesQuietly('database-updating-stalled')).toBe('false')
  })

  it('the internal-error row still says it never retries, and the map still agrees', () => {
    expect(tails.get('Internal error')).toMatch(/Deterministic: this state never retries itself/)
    // The TypeScript mirror of that sentence, read from the map the poller consults at runtime.
    // Flip the map and this fails; delete the sentence and this fails. That is the whole point.
    expect(retriesQuietly('internal-error')).toBe('false')
  })
})

/**
 * The fourth tail, DECLINED at c3-9 and re-homed on c5-6 by name — **now paid in full** (c5-6
 * AC 21, c5-7 AC 13).
 *
 * c3-9's own words for why it was declined: *"there is no connection pill, no backoff and no
 * `disconnected` selection in this repository yet, so any mirror this file asserted would be prose
 * checked against prose."* **All three now exist.** c5-6 shipped the backoff and the `disconnected`
 * selection; c5-7 shipped the pill.
 *
 * So the assertions below come in two layers, and keeping them apart is the point. c5-6's half is
 * about the MECHANISM: it exists, it has the two-gate shape the clause's *"retrying quietly"*
 * implies, and the map the loop reads still says `true`. c5-7's half is about the NOTE: the row
 * promises a retrying-quietly note in the pill, and the pill's shipped `down` copy is what that
 * promise is now held against. Neither half alone would catch the drift the other sees — a pill
 * that said "retrying quietly" over a loop that had stopped, or a loop that retried behind a pill
 * that had stopped saying so.
 *
 * `src/state/socket.test.ts` carries the behavioural half — flip the entry and the loop stops
 * retrying — which is the assertion no source-reading gate can make.
 */
describe('the fourth tail is PAID, not still deferred (AC 15 at c3-9; AC 21 at c5-6; AC 13 at c5-7)', () => {
  /** The loop's own constants, read out of the shipped module rather than imported. See the header. */
  const socketSource = stripComments(sourceOf('src/state/socket.ts'))
  const constant = (name: string): number =>
    Number(
      new RegExp(`export const ${name} = ([\\d_]+)`).exec(socketSource)?.[1]?.replaceAll('_', '') ??
        NaN,
    )

  it('records the disconnected row, and the clause is still there to be honoured', () => {
    expect(tails.get('Disconnected / backend restarted')).toMatch(
      /Retrying-quietly note in the connection pill/,
    )
  })

  it('now has a real backoff behind that clause — the three constants c3-9 had nothing to read', () => {
    // The mirror c3-9 could not write. A "retrying quietly" note is a promise about a mechanism,
    // and until this story there was no mechanism for the note to be true OF.
    expect(constant('SOCKET_BASE_MS')).toBeGreaterThan(0)
    expect(constant('SOCKET_MULTIPLIER')).toBeGreaterThan(1)
    // The ceiling is the difference between a backoff and a countdown to never — without it the
    // note would be true for ten minutes and false forever after.
    expect(constant('SOCKET_CEILING_MS')).toBeGreaterThan(constant('SOCKET_BASE_MS'))
  })

  it('selects `disconnected` from a TWO-GATE threshold, the shape the codebase already uses', () => {
    // Elapsed time AND observed failures, `poller.ts`'s `STALLED_AFTER_MS` +
    // `STALLED_MIN_REFUSALS` pair. One gate alone announces a lost backend to somebody who closed
    // a laptop lid; this file is where the row's copy and that decision are held together.
    expect(constant('DISCONNECTED_AFTER_MS')).toBe(STALLED_AFTER_MS)
    expect(constant('DISCONNECTED_MIN_FAILURES')).toBeGreaterThan(1)
  })

  it('and the map the loop READS still says the state retries', () => {
    // `RETRIES_QUIETLY.disconnected` stopped being a declaration at c5-6: `socket.ts` indexes it
    // to decide whether to keep scheduling behind the panel. Flip it and the loop stops — which
    // `src/state/socket.test.ts` proves by doing exactly that in a try/finally.
    expect(retriesQuietly('disconnected')).toBe('true')
    expect(socketSource).toMatch(/RETRIES_QUIETLY/)
  })

  /**
   * ⚠️ **CONVERTED AT c5-7 (AC 13), NOT DELETED.** This assertion used to read *"leaves the PILL
   * to c5-7, and says so rather than half-asserting it"*, and its whole content was that the row
   * mentions a connection pill and that `socket.ts` does not. That was the honest thing to assert
   * while no pill existed — c3-9 declined the clause for the same reason and c5-6 shipped the
   * backoff without the chrome — and it is the wrong thing to assert now that one does.
   *
   * The clause is *"Retrying-quietly note in the connection pill"*. Both halves of it are now
   * checkable: there is a pill, and it carries a note. So the mirror is the real one — the row's
   * promise against the SHIPPED string — and the deliberate-non-assertion is retired by being
   * paid, which is what `deferred-work.md`'s dw:5354 entry was waiting for.
   */
  const pillWords = stripComments(sourceOf('src/containers/ConnectionPill/copy.ts'))
  const pillDownWords = /down: '([^']*)'/.exec(pillWords)?.[1]

  it('reads the pill’s shipped words at all (non-vacuity for the conversion)', () => {
    // The failure this file's whole header is about: a regex that stopped matching returns
    // `undefined`, and an `undefined` compared with `toContain` throws rather than passing — but
    // an `undefined` fed to a `not.toMatch` would pass silently. Anchored before it is used.
    expect(
      pillDownWords,
      'the down-state words were not found in the pill’s copy module',
    ).toBeDefined()
    expect(pillDownWords!.length).toBeGreaterThan(10)
  })

  it('MIRRORS the retrying-quietly note against the pill’s shipped copy (AC 13)', () => {
    // The row promises the note lives in the pill. This is the assertion that fails if the copy is
    // ever softened to "Backend gone" alone while the artefact still claims a retrying note — the
    // drift no gate could see for two stories.
    expect(tails.get('Disconnected / backend restarted')).toMatch(/Retrying-quietly note/i)
    expect(pillDownWords).toMatch(/retrying quietly/i)
  })

  it('and the note is TRUE of the mechanism, not merely present in the string', () => {
    // Copy checked against copy would be the failure this file exists to prevent, so the note is
    // held to the LOOP as well: the pill may only say "retrying quietly" while the map the loop
    // reads still says the state retries. Flip `RETRIES_QUIETLY.disconnected` and this fails —
    // which is the whole point of the clause having been re-homed twice rather than asserted early.
    expect(retriesQuietly('disconnected')).toBe('true')
    expect(socketSource).toMatch(/RETRIES_QUIETLY/)
  })

  it('and `socket.ts` still contains no `pill` outside its comments', () => {
    // THE HALF THAT STANDS UNCHANGED. The pill reads the loop's field; the loop knows nothing
    // about a pill, and that separation is what stops the announcement chrome from becoming a
    // second writer of the connection status (`systemState.ts:53-60`). c5-7 added a READER, and a
    // reader does not need naming here.
    expect(socketSource).not.toMatch(/pill/i)
  })
})

describe('the parser itself is honest (non-vacuity)', () => {
  it('cuts both fields out, and only those', () => {
    const one = readTails('| Row | Headline: "H." Body: "B one. B two." Tail sentence here. |')
    expect(one.get('Row')).toBe('Tail sentence here.')
  })

  it('ignores a table line that is not a copy row', () => {
    // The Voice-and-Tone table is not the only table in `EXPERIENCE.md`; a row without both
    // fields must not become a tail-less entry that the size pin then counts.
    expect(readTails('| Some other row | Something else entirely |').size).toBe(0)
  })

  it('cannot be satisfied by a commented-out map entry', () => {
    // The reader consumes stripped source, so a deleted-but-still-commented entry reads as the
    // deletion it is — and the live entry beside it is still read (the silent half, AC 26).
    const body = stripComments("  // 'internal-error': false,\n  'internal-error': true,")
    expect(/['"]?internal-error['"]?:\s*(true|false)/.exec(body)?.[1]).toBe('true')
    expect(stripComments("  // 'internal-error': false,")).not.toMatch(/false/)
  })
})

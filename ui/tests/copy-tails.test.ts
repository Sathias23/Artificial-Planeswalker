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
 * The fourth — the disconnected row's *"Retrying-quietly note in the connection pill"* — is
 * **declined here and re-homed on c5-6 by name**, which owns the pill, its backoff and the
 * `disconnected` state. There is nothing in this repository for it to be checked against yet: a
 * gate on it today would assert prose against prose. It is re-homed rather than left as a fourth
 * "candidate home" note, because that is what AC 15 asks for and what the previous three drafts
 * of this item did not do.
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
const DECKS_PATH = /export const DECKS_PATH = '([^']+)'/.exec(sourceOf('src/api/decks.ts'))?.[1]

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

describe('the fourth tail is DECLINED and re-homed, not forgotten (AC 15)', () => {
  it('records the disconnected row as c5-6 work, and asserts only that it is still there', () => {
    // Deliberately weaker than the three above: there is no connection pill, no backoff and no
    // `disconnected` selection in this repository yet, so any mirror this file asserted would be
    // prose checked against prose. What it CAN do is fail if the clause disappears before c5-6
    // arrives to honour it.
    expect(tails.get('Disconnected / backend restarted')).toMatch(
      /Retrying-quietly note in the connection pill/,
    )
    // …and the half c5-6 will read: `disconnected` retries, and this story never selects it.
    expect(retriesQuietly('disconnected')).toBe('true')
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

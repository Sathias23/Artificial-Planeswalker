/**
 * The UI never re-declares a shape the backend already describes — enforced, not documented
 * (NFR-03, AD-12, AC 10).
 *
 * "The REST layer is the schema boundary; the UI never assumes DB schema" is only a rule if
 * something checks it. So this test reads the **`components.schemas` keys out of the committed
 * `openapi.json`** and fails if any tracked TypeScript file outside `src/api/` declares a type
 * of the same name — `interface`, `type`, `class` or `enum`, with or without an `extends`
 * clause.
 *
 * Reading the schema is what gives the rule its authority and its growth: it covers exactly the
 * shapes the backend actually describes today. c3-1's four deck models arrived that way
 * (2026-07-31) — the ban list grew with no edit to the mechanism; the only additions here were
 * two non-vacuity anchors asserting the growth happened (c3-1 review). **c5-1**'s event-envelope
 * payloads will be picked up the same way on the day those routes land. A hard-coded
 * name list would stop growing and become decoration — do not turn it into one. The aliases
 * `src/api/schema.ts` re-exports are read the same way (from that file's `export type` lines),
 * because a derived alias like `ErrorReason` never appears in `components.schemas` yet is
 * exactly the shape a hand-rolled duplicate would drift from (c2-3 review ruling, 2026-07-27).
 *
 * The companion rule (AD-12, story c2-3 Decide-once #2) is checked in the same pass: `src/api/
 * schema.ts` is the single reader of the generated `./types`, so the rest of `ui/src` reaches one
 * import instead of five different paths into a 1,000-line generated file.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

interface OpenApiDocument {
  components?: { schemas?: Record<string, unknown> }
}

const schema = JSON.parse(
  readFileSync(fileURLToPath(new URL('../src/api/openapi.json', import.meta.url)), 'utf8'),
) as OpenApiDocument

/** Every wire shape the backend describes, by its Pydantic class name. */
const wireShapes = Object.keys(schema.components?.schemas ?? {})

/**
 * Every alias `src/api/schema.ts` derives from the generated file (e.g. `ErrorReason`). Read
 * from the file, not hard-coded, for the same growth reason as `wireShapes`: a new alias joins
 * the ban the moment it is exported.
 */
const aliasShapes = [
  ...readFileSync(fileURLToPath(new URL('../src/api/schema.ts', import.meta.url)), 'utf8').matchAll(
    /^export type (\w+)/gm,
  ),
].map((match) => match[1])

const bannedShapes = [...new Set([...wireShapes, ...aliasShapes])]

// This file names banned shapes in prose and constructs the offender-hunting patterns, so it is
// the one file both scans skip — a self-match would be the scan reading its own bait.
const SELF = 'tests/wire-contract.test.ts'

// git is the file authority, not readdir: node_modules, dist and coverage are invisible to it,
// and an offending file is caught the moment it is committed — which is when CI sees it.
// The scan covers every tracked TypeScript root — `src`, `tests`, `config` — not just `src`:
// a test helper is exactly where a hand-rolled duplicate of a wire shape tends to appear first
// (c2-3 review ruling, 2026-07-27).
const trackedFiles = execFileSync('git', ['ls-files', 'src', 'tests', 'config'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)
  .filter((f) => /\.(?:ts|tsx)$/.test(f))

/** Everything except the generated types and the barrel that owns them, for the declaration ban. */
const outsideApi = trackedFiles.filter((f) => !f.startsWith('src/api/') && f !== SELF)

/**
 * Everything except the one sanctioned reader (and the generated `.d.ts` itself), for the
 * single-reader rule — files *inside* `src/api/` are scanned too, so a future
 * `src/api/client.ts` cannot bypass the barrel (c2-3 review).
 */
const importScanned = trackedFiles.filter(
  (f) => f !== 'src/api/schema.ts' && !f.endsWith('.d.ts') && f !== SELF,
)

/** A schema key is interpolated into a RegExp; escape it so `.`/`[` cannot mis-match or crash. */
const escapeRegExp = (name: string) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

describe('wire shapes are declared once, by the backend (NFR-03, AD-12)', () => {
  // The non-vacuity pair for both bans below. A wrong path or a renamed key would leave
  // `wireShapes` empty and make the re-declaration ban pass by finding nothing to look for,
  // and an empty scan list would make it pass by having nothing to look in.
  it('is reading a populated schema, alias list and source tree', () => {
    expect(wireShapes.length).toBeGreaterThan(0)
    expect(wireShapes).toContain('HealthResponse')
    // c3-1's deck models, anchored the same way HealthResponse is. This is NOT the ban list —
    // `bannedShapes` stays derived (landmine 14). It is the non-vacuity anchor, and it is what
    // makes a regeneration that silently drops the deck shapes from `components.schemas` go red
    // in CI rather than quietly shrinking the ban to nothing.
    expect(wireShapes).toContain('DeckSummary')
    expect(wireShapes).toContain('DeckDetail')
    // c3-2's `Card`, joining the same way and for the same reason. The ban itself grew with NO
    // edit to the mechanism — probed 2026-07-31 by staging a `type Card = { x: 1 }` in
    // `src/`, which this suite caught by name. (Staged, because the scan is keyed on
    // `git ls-files`: an untracked plant passes vacuously — a declared limit, in the README's
    // blind-spot map.)
    expect(wireShapes).toContain('Card')
    // c3-3's format-check models, and the first shapes in the ban that come from `src/logic`
    // rather than `src/data` — the ban does not care which layer described them, only that the
    // backend did. Probed 2026-08-01 the same way `Card` was, by staging a
    // `type FormatCheckReport = { x: 1 }` in `src/`, which this suite caught by name.
    expect(wireShapes).toContain('FormatCheckReport')
    expect(wireShapes).toContain('FormatCheckRow')
    // c3-4's active-deck pair. `ActiveDeckRequest` is the first REQUEST body in the whole
    // document — every shape before it was a response — and it joins the ban identically, because
    // the ban is about who DESCRIBED a shape, not about which direction it travels. Probed
    // 2026-08-01 the same way `Card` and the FormatCheck models were, by staging a
    // `type ActiveDeckRequest = { x: 1 }` in `src/`, which this suite caught by name.
    expect(wireShapes).toContain('ActiveDeck')
    expect(wireShapes).toContain('ActiveDeckRequest')
    expect(aliasShapes).toContain('ErrorReason')
    expect(trackedFiles).toContain('src/api/schema.ts')
    expect(outsideApi.length).toBeGreaterThan(0)
    // The import scan provably reaches inside src/api/ — the blind spot it exists to close.
    expect(importScanned).toContain('src/api/schema.test.ts')
  })

  it('declares no wire shape outside src/api/', () => {
    const offenders: string[] = []
    for (const file of outsideApi) {
      const source = readFileSync(new URL(`../${file}`, import.meta.url), 'utf8')
      for (const name of bannedShapes) {
        // Any declaration form that mints the name: `interface Foo`, `type Foo =`, `class Foo`,
        // `enum Foo` — deliberately NOT anchored on what follows the name, so an `extends`
        // clause cannot slip past. The trailing \b keeps `HealthResponseBanner` a non-match.
        const declaration = new RegExp(
          `\\b(?:interface|type|class|enum)\\s+${escapeRegExp(name)}\\b`,
        )
        if (declaration.test(source)) {
          offenders.push(`${file} declares ${name}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  // Decide-once #2. One module indexes the generated file; everything else imports the alias.
  it('imports the generated types through src/api/schema.ts alone', () => {
    // Both static and type-position dynamic forms: `from './types'`, `from '../api/types'`,
    // `import('../api/types')` — with or without an explicit extension.
    const typesImport = /(?:from\s+|import\s*\(\s*)['"][^'"]*\/types(?:\.d\.ts|\.ts|\.js)?['"]/
    const offenders = importScanned.filter((file) =>
      typesImport.test(readFileSync(new URL(`../${file}`, import.meta.url), 'utf8')),
    )
    expect(offenders).toEqual([])
  })
})

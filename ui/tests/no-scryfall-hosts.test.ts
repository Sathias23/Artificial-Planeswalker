/**
 * No file under `ui/src` reaches for a Scryfall host — the SPA's half of "every image comes from
 * the app's own origin" (c3-5 AC 27; AD-11, UX-DR36; epic AC `:1706-1708`).
 *
 * The epic's rule is satisfied *negatively* in c3-5 — no frontend fetch code exists until c4-4 —
 * and this scan is what keeps that true when c4-4 lands: the tile that renders an image must ask
 * `/api/card-image/{id}`, never the CDN. Keyed on the host FAMILY (`<subdomain>.scryfall.io|com`),
 * not on remembered members (standing agreement: ban the family), so `api.scryfall.com`,
 * `cards.scryfall.io`, `errors.scryfall.com` and any future `c1.scryfall.com` are all one rule.
 *
 * A SUBDOMAIN is required by the pattern on purpose: the Footer's Scryfall attribution
 * (`https://scryfall.com/docs/api`, `src/components/Footer/copy.ts`) is a shipped, deliberate
 * link to Scryfall's *site*, not a data fetch, and the bare apex host is how it stays legal while
 * every data host stays banned. The wire-side half of this rule — nothing in `openapi.json`
 * carries a Scryfall host — lives in `tests/unit/companion/test_openapi_contract.py`; this scan
 * covers the committed `src/api/types.d.ts` and `src/api/openapi.json` too, because both are
 * tracked under `src/`.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

/** Any subdomained Scryfall host, whatever the subdomain — the family, not a member list. */
const SCRYFALL_HOST = /[a-z0-9-]+\.scryfall\.(?:io|com)/i

// git is the file authority, not readdir, for the same reason wire-contract.test.ts gives:
// node_modules and dist are invisible to it, and an offender is caught when it is committed.
// (Same declared limit too: an untracked plant passes vacuously — README blind-spot map.)
const scannedFiles = execFileSync('git', ['ls-files', 'src'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)

describe('no Scryfall host reaches ui/src (AC 27; AD-11, UX-DR36)', () => {
  // The non-vacuity pair (AC 29): the pattern provably fires on every host class it exists to
  // catch, and provably spares the one shipped apex-host use it exists to spare.
  it('sees a planted occurrence of each banned host class', () => {
    expect('https://cards.scryfall.io/normal/front/a/b/c.jpg?123').toMatch(SCRYFALL_HOST)
    expect('https://errors.scryfall.com/soon.jpg').toMatch(SCRYFALL_HOST)
    expect('https://api.scryfall.com/cards/named?exact=x').toMatch(SCRYFALL_HOST)
    // Case cannot smuggle a host past the scan.
    expect('HTTPS://CARDS.SCRYFALL.IO/x.jpg').toMatch(SCRYFALL_HOST)
    // ...and the two spellings the scan must NOT fire on: the shipped attribution link's apex
    // host, and the path parameter's snake_case identifier.
    expect('https://scryfall.com/docs/api').not.toMatch(SCRYFALL_HOST)
    expect('/api/card-image/{scryfall_id}').not.toMatch(SCRYFALL_HOST)
  })

  it('is scanning a populated source tree that includes the generated files', () => {
    expect(scannedFiles.length).toBeGreaterThan(0)
    expect(scannedFiles).toContain('src/api/openapi.json')
    expect(scannedFiles).toContain('src/api/types.d.ts')
    expect(scannedFiles).toContain('src/components/Footer/copy.ts')
  })

  it('finds no Scryfall host in any tracked file under src/', () => {
    const offenders = scannedFiles.flatMap((file) => {
      const match = SCRYFALL_HOST.exec(readFileSync(new URL(`../${file}`, import.meta.url), 'utf8'))
      return match ? [`${file} contains ${match[0]}`] : []
    })
    expect(offenders).toEqual([])
  })
})

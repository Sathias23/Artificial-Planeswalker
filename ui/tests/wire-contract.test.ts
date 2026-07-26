/**
 * The UI never re-declares a shape the backend already describes — enforced, not documented
 * (NFR-03, AD-12, AC 10).
 *
 * "The REST layer is the schema boundary; the UI never assumes DB schema" is only a rule if
 * something checks it. So this test reads the **`components.schemas` keys out of the committed
 * `openapi.json`** and fails if any tracked file under `ui/src` outside `src/api/` declares an
 * `interface` or `type` alias of the same name.
 *
 * Reading the schema is what gives the rule its authority and its growth: it covers exactly the
 * shapes the backend actually describes today, and it picks up **c3-1**'s deck models and
 * **c5-1**'s event-envelope payloads on the day those routes land, with no edit here. A hard-coded
 * name list would stop growing and become decoration — do not turn it into one.
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

// git is the file authority, not readdir: node_modules, dist and coverage are invisible to it,
// and an offending file is caught the moment it is committed — which is when CI sees it.
const sourceFiles = execFileSync('git', ['ls-files', 'src'], { cwd: uiRoot, encoding: 'utf8' })
  .split('\n')
  .filter(Boolean)
  .filter((f) => /\.(?:ts|tsx)$/.test(f))

/** Everything under `src/` except the generated types and the barrel that owns them. */
const outsideApi = sourceFiles.filter((f) => !f.startsWith('src/api/'))

describe('wire shapes are declared once, by the backend (NFR-03, AD-12)', () => {
  // The non-vacuity pair for both bans below. A wrong path or a renamed key would leave
  // `wireShapes` empty and make the re-declaration ban pass by finding nothing to look for,
  // and an empty `outsideApi` would make it pass by having nothing to look in.
  it('is reading a populated schema and a populated source tree', () => {
    expect(wireShapes.length).toBeGreaterThan(0)
    expect(wireShapes).toContain('HealthResponse')
    expect(sourceFiles).toContain('src/api/schema.ts')
    expect(outsideApi.length).toBeGreaterThan(0)
  })

  it('declares no wire shape outside src/api/', () => {
    const offenders: string[] = []
    for (const file of outsideApi) {
      const source = readFileSync(new URL(`../${file}`, import.meta.url), 'utf8')
      for (const name of wireShapes) {
        // `interface Foo` / `type Foo =`, with the name bounded so `HealthResponseBanner`
        // is not a false positive.
        const declaration = new RegExp(`\\b(?:interface|type)\\s+${name}\\b\\s*(?:=|\\{|<)`)
        if (declaration.test(source)) {
          offenders.push(`${file} declares ${name}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  // Decide-once #2. One module indexes the generated file; everything else imports the alias.
  it('imports the generated types through src/api/schema.ts alone', () => {
    const offenders = outsideApi.filter((file) =>
      /from\s+['"][^'"]*api\/types['"]/.test(
        readFileSync(new URL(`../${file}`, import.meta.url), 'utf8'),
      ),
    )
    expect(offenders).toEqual([])
  })
})
